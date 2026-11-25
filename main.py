import argparse
import os
import sys

import yaml

from agent.apply import apply
from agent.db import DB
from agent.discover import discover
from agent.rag import Index


def load_profile(path="data/profile.yaml"):
    if not os.path.exists(path):
        sys.exit("Copy data/profile.example.yaml to data/profile.yaml and fill it in first.")
    return yaml.safe_load(open(path))


def cmd_discover(a):
    prof, db = load_profile(), DB()
    jobs = [j for j in discover(prof) if not db.seen(j.key)]
    for j in jobs:
        print(f"{j.company:<20} {j.title}  ->  {j.url}")
    print(f"\n{len(jobs)} new matching jobs")


def cmd_run(a):
    prof, db, index = load_profile(), DB(), Index.from_dir()
    cap = prof.get("preferences", {}).get("max_applications_per_company", 3)
    done = 0
    for j in discover(prof):
        if done >= a.limit:
            break
        if db.seen(j.key) or db.company_count(j.company) >= cap:
            continue
        try:
            status, notes = apply(j, prof, index, a.mode, headless=not a.show)
        except KeyboardInterrupt:
            status, notes = "skipped", "skipped by user"
        except Exception as e:
            status, notes = "error", str(e)[:200]
        db.save(j, status, notes)
        done += 1
        print(f"[{status}] {j.company} - {j.title}")


def cmd_status(a):
    for row in DB().rows(a.status):
        print(" | ".join(str(x) for x in row))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(required=True)
    sub.add_parser("discover").set_defaults(fn=cmd_discover)
    r = sub.add_parser("run")
    r.add_argument("--mode", choices=["review", "auto", "dry"], default="dry")
    r.add_argument("--limit", type=int, default=10)
    r.add_argument("--show", action="store_true", help="show the browser window")
    r.set_defaults(fn=cmd_run)
    s = sub.add_parser("status")
    s.add_argument("--status")
    s.set_defaults(fn=cmd_status)
    a = ap.parse_args()
    a.fn(a)
