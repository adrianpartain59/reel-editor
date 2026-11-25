"""The audio map: what is audible when, and the rules that keep sound effects tidy.

Built by mix.py, checked by qa.py, written to work/out/<variant>/audio_map.json and audio_map.txt (one line per
0.25 s: is the speaker talking, which effects are playing). Rules:

  NEVER ALTERED   every effect plays whole, at its own speed: never sped up, slowed down, cut short or cut into.
                  Where one can't fit, it is left out. Fewer effects beat effects used the wrong way.
  ITS OWN JOB     each sound has usage rules (pack.json "rules", read through rules_of): which events may use it
                  (`events`), which always get it (`must`), where (`hook`, `cta`, anywhere), how often (`min_gap`
                  seconds between uses, `max` per reel). A cue that breaks its sound's rules is dropped.
  ONE AT A TIME   the loud part of one foreground effect (until it falls LOUD_DB under its peak) never overlaps
                  another's; the tail may ring under the next. On a clash the higher-priority cue keeps its place
                  (`must` events first), the other is dropped whole.
  BACKGROUND      sounds marked `background` (the whoosh) are quiet, may repeat freely and play under the others.
  NO PILE-UPS     at most MAX_PER_SEC foreground effects starting in any 1 s window.
"""
import json
import numpy as np

MAX_PER_SEC = 3
WHOOSH_DB = -3.0      # whoosh-family sounds sit this far under their category level (they are the background bed)
LOUD_DB = -20.0       # a foreground sound's "loud part" ends when it falls this far under its own peak
WHOOSH_CATS = ("whoosh", "whoosh_heavy", "swish", "swipe", "reverse", "riser")
RUN_CATS = ("key", "tick", "type_key", "ui_tick", "counting")


def family(name, cat=None):
    c = cat or (name[4:].rsplit("_", 1)[0] if name.startswith("lib:") else name)
    if c in RUN_CATS or "key" in c or "tick" in c: return "run"
    if c in WHOOSH_CATS or any(w in c for w in ("whoosh", "swish", "swipe", "reverse", "riser", "suck")): return "whoosh"
    return "fx"


def audible_len(x, sr, floor_db=-30.0):
    """Seconds until the sound falls below floor_db under its own peak for good."""
    e = np.sqrt(np.mean(x ** 2, axis=1)) if x.ndim == 2 else np.abs(x)
    w = max(1, int(0.01 * sr)); n = len(e) // w
    if n == 0: return len(e) / sr
    env = e[: n * w].reshape(n, w).max(1); pk = env.max() + 1e-12
    above = np.nonzero(env > pk * 10 ** (floor_db / 20))[0]
    return (above[-1] + 1) * w / sr if len(above) else 0.0


def event_ok(key, events):
    """Does cue key ("phone_in:rise", "tr:whip", "fx:flash", "title") match a rule's event list?"""
    k = str(key)
    return any((e.endswith(":") and k.startswith(e)) or k == e or k.split(":")[0] == e for e in events)


def schedule(cues, sr, load, rules_of=lambda cat: {}, hook_end=0.0, duration=None):
    """cues: [t, name, extra_db, span, prio, key]. load(name) -> (x (n,2), sync_s, cat).
    Returns (placed, dropped). Cues claim time in priority order, so the cues a rule says must sound go first."""
    def prio_of(c, rules):
        key = c[5] if len(c) > 5 else ""
        if key == "cta": return 10.0                     # the CTA ding outranks even a text pop: on the CTA it replaces it
        return 9.0 if event_ok(key, rules.get("must", [])) else (c[4] if len(c) > 4 else 1.0)
    cand, dropped = [], []
    for c in cues:
        t, name, db = c[0], c[1], c[2]; key = c[5] if len(c) > 5 else ""
        got = load(name)
        if got is None: dropped.append({"t": t, "name": name, "why": "missing file"}); continue
        x, sync, cat = got; fam = family(name, cat); rules = rules_of(cat) or {}
        if rules.get("events") and not event_ok(key, rules["events"]):
            dropped.append({"t": t, "name": name, "why": f"{cat} is not for {key}"}); continue
        where = rules.get("where", "any")
        if where == "hook" and t >= hook_end: dropped.append({"t": t, "name": name, "why": f"{cat} only plays in the hook"}); continue
        if where == "cta" and key != "cta": dropped.append({"t": t, "name": name, "why": f"{cat} only plays on the CTA"}); continue
        start = t - sync
        if start < 0: dropped.append({"t": t, "name": name, "why": "would start before the reel (no cutting its front)"}); continue
        dur = len(x) / sr
        if duration and start + audible_len(x, sr, LOUD_DB) > duration:
            dropped.append({"t": t, "name": name, "why": "its loud part would run past the end of the reel"}); continue
        cand.append({"t": round(t, 3), "start": start, "end": start + dur, "dur": round(dur, 3), "name": name, "cat": cat,
                     "family": fam, "key": key, "prio": prio_of(c, rules), "speed": 1.0, "rules": rules,
                     "extra_db": db + (WHOOSH_DB if fam == "whoosh" else 0.0), "x": x, "orig": start, "lead": sync,
                     "span": dur, "loud_end": start + audible_len(x, sr, LOUD_DB), "bg": bool(rules.get("background"))})
    placed = []
    for c in sorted(cand, key=lambda c: (-c["prio"], c["t"])):
        r = c["rules"]; same = [p for p in placed if p["cat"] == c["cat"]]
        if r.get("max") is not None and len(same) >= r["max"]:
            dropped.append({"t": c["t"], "name": c["name"], "why": f"{c['cat']}: at most {r['max']} a reel"}); continue
        gap = r.get("min_gap", 0.15)
        near = [p for p in same if abs(p["t"] - c["t"]) < gap]     # 0.15 s by default; a typing run sets its own
        if near:
            dropped.append({"t": c["t"], "name": c["name"], "why": f"{c['cat']} used {abs(near[0]['t'] - c['t']):.1f}s away (min {gap}s)"}); continue
        if not c["bg"]:
            # the key presses of one typing run overlap each other like real typing; they still never land on other sounds
            hit = [p for p in placed if not p["bg"] and c["start"] < p["loud_end"] and p["start"] < c["loud_end"]
                   and not (c["family"] == "run" and p["family"] == "run" and p["cat"] == c["cat"])]
            if hit:
                dropped.append({"t": c["t"], "name": c["name"], "why": f"would play over {hit[0]['name']} at {hit[0]['t']:.2f}s"}); continue
            win = [p for p in placed if not p["bg"] and p["family"] != "run" and abs(p["t"] - c["t"]) < 1.0]
            if c["family"] != "run" and len(win) >= MAX_PER_SEC:
                dropped.append({"t": c["t"], "name": c["name"], "why": f"more than {MAX_PER_SEC} effects in 1 s"}); continue
        placed.append(c)
    for p in placed: p.pop("rules", None)
    return sorted(placed, key=lambda p: p["start"]), sorted(dropped, key=lambda d: d["t"])


def render(placed, n, sr, gain_of):
    """Mix the placed cues into an (n, 2) bus, each sound whole."""
    bus = np.zeros((n, 2))
    for p in placed:
        seg = p["x"]; i0 = int(round(p["start"] * sr))
        if len(seg) == 0: continue
        m = max(0, min(len(seg), n - i0)); bus[i0:i0 + m] += seg[:m] * 10 ** (gain_of(p) / 20)
        p["gain_db"] = round(gain_of(p), 1)
    return bus


def write(path_json, path_txt, duration, speech, placed, dropped, music=None, hook_end=None):
    cues = [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in p.items() if k != "x"} for p in placed]
    js = {"duration": round(duration, 3), "speech": [[round(a, 2), round(b, 2)] for a, b in speech],
          "cues": cues, "dropped": dropped, "music": music, "hook_end": hook_end}
    path_json.write_text(json.dumps(js, indent=1))
    lines = ["time   voice  effect"]
    t = 0.0
    while t < duration:
        talk = any(a <= t < b for a, b in speech)
        now = [p for p in placed if p["start"] <= t < p["end"]]
        lines.append(f"{t:6.2f}  {'TALK ' if talk else '  -  '}  {', '.join(p['name'] for p in now) or ''}")
        t += 0.25
    path_txt.write_text("\n".join(lines) + "\n")
    return js


def check(js, rules_of=None):
    """Problems with the sound, for qa.py: [(level, message), ...]."""
    out = []; cues = js["cues"]
    alt = [c for c in cues if abs((c["end"] - c["start"]) - c.get("dur", c["end"] - c["start"])) > 0.005 or c.get("speed", 1) != 1]
    out.append(("FAIL" if alt else "PASS", "every effect plays whole, at its own speed" if not alt else
                "effects cut or re-timed: " + ", ".join(f"{c['name']} {c['t']:.1f}s" for c in alt[:4])))
    fg = [c for c in cues if not c.get("bg")]
    overl = [(a["name"], b["name"], round(b["start"], 2)) for i, a in enumerate(fg) for b in fg[i + 1:]
             if b["start"] < a.get("loud_end", a["end"]) - 0.005 and a["start"] < b.get("loud_end", b["end"])
             and not (a["family"] == "run" and b["family"] == "run" and a["cat"] == b["cat"])]
    out.append(("FAIL" if overl else "PASS", "one foreground effect at a time" if not overl else
                "effects overlap: " + ", ".join(f"{a} + {b} at {t}s" for a, b, t in overl[:4])))
    if rules_of:
        bad = []
        for c in cues:
            r = rules_of(c["cat"]) or {}
            if r.get("events") and not event_ok(c.get("key", ""), r["events"]): bad.append(f"{c['cat']} on {c.get('key')}")
            if r.get("where") == "hook" and c["t"] >= js.get("hook_end", 1e9): bad.append(f"{c['cat']} outside the hook")
        from collections import Counter
        for cat, n in Counter(c["cat"] for c in cues).items():
            r = rules_of(cat) or {}
            if r.get("max") is not None and n > r["max"]: bad.append(f"{cat} x{n} (max {r['max']})")
        out.append(("FAIL" if bad else "PASS", "every effect follows its sound's rules" if not bad else "rule breaks: " + ", ".join(bad[:5])))
    ts = [c["t"] for c in fg if c["family"] != "run" and c.get("cat") not in ("reverse", "riser")]
    dense = [t for t in ts if sum(1 for u in ts if t <= u < t + 1.0) > MAX_PER_SEC]
    out.append(("WARN" if dense else "PASS", f"at most {MAX_PER_SEC} foreground effects per second" if not dense else
                f"crowded at {dense[0]:.1f}s"))
    return out
