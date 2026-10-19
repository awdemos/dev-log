#!/usr/bin/env python3
"""Daily dev-log journal.

Scans git repos under ~/code for commits made today (America/Chicago),
appends a notes/YYYY-MM-DD.md summary and per-repo log entries to this
repository (one commit each), and pushes. Idempotent: repos already covered
in today's log file are skipped, and a day with no activity is a no-op.
"""

import collections
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CODE = Path.home() / "code"
SCAN_ROOTS = [CODE]
EXCLUDE = {REPO, CODE / "code-attic"}
CAP = 15
NAME = "Drew the AI Guy"
EMAIL = "159745380+awdemos@users.noreply.github.com"
TZ = "America/Chicago"


def local_today() -> str:
    out = subprocess.run(
        ["bash", "-c", f'TZ={TZ} date +%F'], capture_output=True, text=True
    )
    return out.stdout.strip()


def find_repos(root: Path):
    for dirpath, dirnames, _ in os.walk(root):
        p = Path(dirpath)
        if p in EXCLUDE or any(p.is_relative_to(e) for e in EXCLUDE):
            dirnames[:] = []
            continue
        if ".git" in dirnames:
            yield p
            dirnames[:] = [d for d in dirnames if d != ".git"]
            continue
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]


def activity(date: str) -> dict[str, list[str]]:
    per_repo: dict[str, list[str]] = collections.defaultdict(list)
    for repo in find_repos(CODE):
        out = subprocess.run(
            ["git", "-C", str(repo), "log", f"--since={date} 00:00", f"--until={date} 23:59:59",
             "--format=%h", "--date=format-local:%Y-%m-%d"],
            env={**os.environ, "TZ": TZ},
            capture_output=True, text=True,
        )
        if out.returncode == 0 and out.stdout.strip():
            per_repo[str(repo)] = out.stdout.split()
    return per_repo


def git(*args: str) -> None:
    subprocess.run(["git", "-C", str(REPO), *args], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    date = local_today()
    repos = activity(date)
    if not repos:
        print(f"{date}: no activity, nothing to journal")
        return 0

    ordered = sorted(repos.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    total = sum(len(v) for v in repos.values())

    note = REPO / "notes" / f"{date}.md"
    entries = REPO / "log" / f"{date}.log"

    if not note.exists():
        lines = [f"# {date}", "",
                 f"{total} commits across {len(repos)} repos.",
                 "", "## Repos", ""]
        lines += [f"- `{r}`: {len(hs)} commits" for r, hs in ordered]
        note.write_text("\n".join(lines) + "\n")
        git("add", "notes")
        git("commit", "-m", f"dev log {date}: {total} commits across {len(repos)} repos")
        print(f"created {note.name}: {total} commits across {len(repos)} repos")

    existing = entries.read_text() if entries.exists() else ""
    new_entries = [(r, hs) for r, hs in ordered if f"- {r}:" not in existing][: CAP - 1]
    for repo, hashes in new_entries:
        with entries.open("a") as f:
            shown = " ".join(hashes[:10])
            more = f" … (+{len(hashes) - 10})" if len(hashes) > 10 else ""
            f.write(f"- {repo}: {len(hashes)} commits [{shown}{more}]\n")
        short = repo.replace(str(Path.home()) + "/", "~/")
        git("add", "log")
        git("commit", "-m", f"{date} {short}: {len(hashes)} commits")
        print(f"entry: {short} ({len(hashes)} commits)")

    if not note.exists() and not new_entries:
        print("nothing new")
        return 0
    git("push")
    print("pushed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
