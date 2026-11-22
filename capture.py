#!/usr/bin/env python3
"""Capture safe, concise Git metadata for Handoff Kit; never reads file contents."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def git(
    repo: str | Path, *args: str, check: bool = True, env: dict[str, str] | None = None
) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if check and result.returncode != 0:
        message = result.stderr.strip() or f"git {' '.join(args)} failed"
        raise RuntimeError(message)
    return result.stdout.rstrip("\n")


def capture_repository(repo: str | Path) -> dict[str, Any]:
    """Return repository metadata only: no diffs, file contents, or environment values."""
    try:
        # Use a stable diagnostic for the repository discovery check.
        root_text = git(repo, "rev-parse", "--show-toplevel", env={**os.environ, "LC_ALL": "C"})
    except RuntimeError as exc:
        if str(exc).startswith("fatal: not a git repository ("):
            raise RuntimeError(
                "Handoff Kit needs to run inside a Git repository. cd into your project and try again."
            ) from exc
        raise
    root = Path(root_text)
    raw_status = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    changed_files: list[str] = []
    entries = raw_status.split("\0")
    index = 0
    while index < len(entries):
        line = entries[index]
        index += 1
        if len(line) >= 4:
            status = line[:2]
            path = line[3:]
            if path:
                changed_files.append(path)
            # In porcelain -z output, renames/copies use a second NUL-delimited
            # record for the original path; both paths changed and belong here.
            if "R" in status or "C" in status:
                if index < len(entries):
                    original_path = entries[index]
                    index += 1
                    if original_path:
                        changed_files.append(original_path)
    changed_files = sorted(set(changed_files))

    head = git(root, "rev-parse", "--short=12", "HEAD", check=False).strip() or None
    branch = git(root, "branch", "--show-current", check=False).strip()
    if not branch:
        branch = f"detached@{head}" if head else "unborn"

    diff_summary = ""
    if head:
        diff_summary = git(root, "diff", "--stat", "HEAD", check=False).strip()
    recent_raw = git(root, "log", "-n", "5", "--pretty=format:%h%x09%s", check=False)
    recent_commits = []
    for line in recent_raw.splitlines():
        short_hash, separator, subject = line.partition("\t")
        recent_commits.append({"hash": short_hash, "subject": subject if separator else ""})

    return {
        "name": root.name,
        "branch": branch,
        "head": head or "(no commit yet)",
        "dirty": bool(changed_files),
        "changed_files": changed_files,
        "diff_summary": diff_summary or ("Working tree clean" if not changed_files else "Changed paths recorded; no diff summary available"),
        "recent_commits": recent_commits,
    }


def capture_snapshot(repo: str | Path) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "captured_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "repository": capture_repository(repo),
    }


def compare_repositories(expected: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    checks = []
    for key, label in (("branch", "branch"), ("head", "HEAD commit"), ("changed_files", "changed file paths")):
        expected_value = expected.get(key)
        current_value = current.get(key)
        if key == "changed_files":
            expected_value = sorted(expected_value or [])
            current_value = sorted(current_value or [])
        checks.append({
            "item": label,
            "matches": expected_value == current_value,
            "captured": expected_value,
            "current": current_value,
        })
    return {"stale": any(not check["matches"] for check in checks), "checks": checks}


def emit(data: dict[str, Any], destination: str | None) -> None:
    rendered = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if destination:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
        print(f"Wrote {path}")
    else:
        sys.stdout.write(rendered)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Capture Git metadata for a portable Handoff Kit capsule; file contents are never read."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    snapshot_parser = subparsers.add_parser("snapshot", help="capture repository metadata as JSON")
    snapshot_parser.add_argument("--repo", default=".", help="repository path (default: current directory)")
    snapshot_parser.add_argument("--out", help="write JSON to this path instead of stdout")
    check_parser = subparsers.add_parser("check", help="compare a capsule snapshot with the current repository")
    check_parser.add_argument("--repo", default=".", help="repository path (default: current directory)")
    check_parser.add_argument("--capsule", required=True, help="Handoff Kit capsule or snapshot JSON")
    args = parser.parse_args(argv)

    try:
        if args.command == "snapshot":
            emit(capture_snapshot(args.repo), args.out)
            return 0

        try:
            capsule = json.loads(Path(args.capsule).read_text(encoding="utf-8"))
        except FileNotFoundError:
            print(
                f"handoff-kit: Capsule file not found: {args.capsule}. "
                "Check the --capsule path and try again.",
                file=sys.stderr,
            )
            return 1
        if not isinstance(capsule, dict):
            print("handoff-kit: capsule must be a JSON object.", file=sys.stderr)
            return 1
        expected = capsule.get("repository")
        if not isinstance(expected, dict):
            print("This file has no repository snapshot. Import a Git snapshot before exporting the capsule.", file=sys.stderr)
            return 1
        current = capture_repository(args.repo)
        report = compare_repositories(expected, current)
        if report["stale"]:
            print("STALE — repository metadata differs from the saved handoff.")
        else:
            print("CURRENT — branch, HEAD, and changed file paths match the saved handoff.")
        for check in report["checks"]:
            status = "OK" if check["matches"] else "CHANGED"
            print(f"{status:7} {check['item']}: captured={check['captured']!r}; current={check['current']!r}")
        return 2 if report["stale"] else 0
    except (OSError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"handoff-kit: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
