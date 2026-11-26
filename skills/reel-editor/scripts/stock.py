#!/usr/bin/env python3
"""Real footage for the Vector art style: free stock video from Mixkit, Stock Video Free License only.

  stock.py search PROJECT "finish line" marathon ...   ids and titles per search, and a sheet of thumbnails to pick from
                                                      (PROJECT/media/_search/<term>.jpg, each tile numbered with its id)
  stock.py get PROJECT ID NAME                         checks the item's licence, downloads the 720p clip to
                                                      PROJECT/media/NAME.mp4 and records it in PROJECT/media/credits.json
  stock.py still PROJECT NAME SECONDS                  one frame of a clip as PROJECT/media/NAME.jpg (a real photo)

Why Mixkit: Unsplash answers scripts with a bot check (never bypass it), Pexels and Pixabay refuse them. Mixkit's FAQ
(read it yourself before relying on this summary): videos under the Free License can be used in commercial projects,
social media marketing included, with no attribution. Videos under the Restricted License are for personal projects
only, so `get` refuses them: every item page says which one it is (data-license="videoFree" or "videoRestricted").
Clips go inside the reel only, never re-shared as files. Tell the user what will be downloaded before `get`.
"""
import json, re, subprocess, sys, urllib.error, urllib.request
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"}
SITE = "https://mixkit.co"


def fetch(url, binary=False):
    """Paced (Mixkit answers 429 to bursts): a pause before each request, and a longer wait and retry on 429."""
    import time
    for wait in (0, 20, 60, 120):
        time.sleep(wait or .8)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r: b = r.read()
            return b if binary else b.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code != 429: raise
    raise SystemExit("Mixkit keeps answering 429 (too many requests); try again in a few minutes")


def slug(term):
    return re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")


def search(proj, terms):
    out = Path(proj) / "media/_search"; out.mkdir(parents=True, exist_ok=True)
    from PIL import Image, ImageDraw
    for term in terms:
        html = fetch(f"{SITE}/free-stock-video/discover/{slug(term)}/")
        items = list(dict.fromkeys(re.findall(r"free-stock-video/([a-z0-9-]+)-(\d+)/", html)))
        idx = out / "index.json"; pages = json.loads(idx.read_text()) if idx.exists() else {}
        pages.update({i: f"{SITE}/free-stock-video/{name}-{i}/" for name, i in items}); idx.write_text(json.dumps(pages, indent=0))
        lic = licences(out, [i for _, i in items[:24]], pages)
        free = [(n, i) for n, i in items[:24] if lic.get(i) == "videoFree"]
        print(f"== {term}: {len(items)} found, {len(free)} under the Free License (the Restricted ones are left out)")
        tiles = []
        for name, i in free:
            print(f"  {i:>6}  {name.replace('-', ' ')}")
            try:
                im = Image.open(__import__("io").BytesIO(fetch(f"https://assets.mixkit.co/videos/{i}/{i}-thumb-360-0.jpg", True))).convert("RGB")
            except Exception:
                continue
            im.thumbnail((320, 320)); t = Image.new("RGB", (320, 210), "black"); t.paste(im, ((320 - im.width) // 2, (210 - im.height) // 2))
            d = ImageDraw.Draw(t); d.rectangle((0, 0, 70, 22), fill="black"); d.text((4, 4), i, fill="yellow"); tiles.append(t)
        if tiles:
            cols = 4; s = Image.new("RGB", (cols * 320, ((len(tiles) + cols - 1) // cols) * 210), "white")
            for k, t in enumerate(tiles): s.paste(t, ((k % cols) * 320, (k // cols) * 210))
            s.save(out / f"{slug(term)}.jpg", quality=85); print(f"  sheet {out / (slug(term) + '.jpg')}")


def licences(out, ids, pages):
    """Each item page names its licence; cached in _search/licences.json."""
    f = out / "licences.json"; known = json.loads(f.read_text()) if f.exists() else {}
    from concurrent.futures import ThreadPoolExecutor
    def one(i):
        try: return i, (re.findall(r'data-license="(video[A-Za-z]+)"', fetch(pages[i])) or ["unknown"])[0]
        except Exception: return i, "unknown"
    todo = [i for i in ids if i not in known]
    with ThreadPoolExecutor(1) as ex: known.update(dict(ex.map(one, todo)))
    f.write_text(json.dumps(known, indent=0)); return known


def get(proj, i, name):
    media = Path(proj) / "media"; media.mkdir(parents=True, exist_ok=True)
    idx = media / "_search/index.json"; pages = json.loads(idx.read_text()) if idx.exists() else {}
    if i not in pages: raise SystemExit(f"item {i}: not in an earlier search; run `stock.py search` first")
    page = pages[i]
    html = fetch(page)
    lic = re.findall(r'data-license="(video[A-Za-z]+)"', html)
    if "videoFree" not in lic or "videoRestricted" in lic:
        raise SystemExit(f"item {i}: licence {lic or 'unknown'}, not the Stock Video Free License; pick another clip")
    title = re.search(r"<title>([^<|]+)", html); title = (title.group(1).strip() if title else page)
    url = f"https://assets.mixkit.co/videos/{i}/{i}-720.mp4"; dst = media / f"{name}.mp4"
    dst.write_bytes(fetch(url, True))
    cred = media / "credits.json"; c = json.loads(cred.read_text()) if cred.exists() else {}
    c[name] = {"id": i, "title": title, "page": page, "file": url, "license": "Mixkit Stock Video Free License"}
    cred.write_text(json.dumps(c, indent=1))
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height", "-of", "csv=p=0", str(dst)], capture_output=True, text=True).stdout.split()
    print(f"{name}: {title}  {' '.join(p)}  {dst.stat().st_size / 1e6:.1f} MB  ({page})")


def still(proj, name, sec):
    media = Path(proj) / "media"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(sec), "-i", str(media / f"{name}.mp4"), "-frames:v", "1", "-q:v", "2", str(media / f"{name}.jpg")], check=True)
    print(media / f"{name}.jpg")


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 3 and a[0] == "search": search(a[1], a[2:])
    elif len(a) == 4 and a[0] == "get": get(a[1], a[2], a[3])
    elif len(a) == 4 and a[0] == "still": still(a[1], a[2], float(a[3]))
    else: print(__doc__)
