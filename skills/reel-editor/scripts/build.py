#!/usr/bin/env python3
"""Render, mix and QA every hook variant (or one).

  build.py PROJECT [--variant h1]
"""
import argparse, subprocess, sys
from pathlib import Path
from common import load

HERE = Path(__file__).parent


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--variant", default=None)
    a = ap.parse_args()
    plan = load(Path(a.project).expanduser() / "plan.json")
    variants = [a.variant] if a.variant else list(plan["hooks"].keys())
    ok = True
    for v in variants:
        for step in (["compose.py", "--variant", v], ["mix.py", "--variant", v], ["qa.py", "--variant", v]):
            print(f"== {v}: {step[0]}", flush=True)
            r = subprocess.run([sys.executable, str(HERE / step[0]), a.project, *step[1:]])
            if r.returncode != 0:
                ok = False
                if step[0] != "qa.py": sys.exit(r.returncode)
        if plan.get("cover") or plan["hooks"][v].get("cover"):
            subprocess.run([sys.executable, str(HERE / "compose.py"), a.project, "--variant", v, "--cover"])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
