# Handoff Kit

A small, local-first handoff for coding-agent work. Keep the task goal, decisions, checks, blockers, and next action together with a compact Git snapshot, then export a portable Markdown or JSON file.

**Status:** early prototype. It is deliberately manual: it does not capture chats, generate summaries with a model, sync between devices, or integrate with agent platforms.

- [Try the browser demo](https://saurabhkumarozp61-cmd.github.io/agent-handoff-kit/demo/)
- [Project website](https://saurabhkumarozp61-cmd.github.io/agent-handoff-kit/)

## What it does

1. Write or edit a short handoff in the browser UI.
2. Optionally import a Git snapshot produced by `capture.py`.
3. Export the handoff as Markdown or JSON.
4. Later, compare the saved snapshot with the current checkout; the CLI reports `CURRENT` or `STALE` based on branch, commit, and changed paths.

The browser app has no backend or model/API calls. Drafts are saved in that browser's local storage. The hosted demo serves static files; it does not receive your handoff data. The CLI reads Git metadata only—not source-file contents, environment variables, terminal history, or chat transcripts. However, exported file paths and commit subjects can reveal project details, so review a snapshot and handoff before sharing them.

## Run locally

Requirements: Python 3.9+ and a modern browser. No package installation is needed.

```bash
git clone https://github.com/saurabhkumarozp61-cmd/agent-handoff-kit.git
cd agent-handoff-kit
python3 -m http.server 4173 --bind 127.0.0.1
```

Open <http://127.0.0.1:4173>. The browser demo is also available under `docs/demo/` for GitHub Pages hosting.

## Capture and check a snapshot

From a Git checkout, create a snapshot JSON file:

```bash
python3 capture.py snapshot --repo /path/to/project --out /tmp/repo-snapshot.json
```

Import that file in the browser app, add the human-written context, and export a handoff JSON. To compare a later checkout with the saved repository snapshot:

```bash
python3 capture.py check --repo /path/to/project --capsule /path/to/handoff.json
```

Exit code `0` means the saved branch, commit, and changed-file paths match; exit code `2` means the snapshot is stale. The warning is a prompt to review the handoff, not proof that its task context is wrong.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Scope and limitations

Handoff Kit is a user-controlled file workflow, not an agent memory engine. Notes are human-entered, tests are not independently verified by the app, and no automatic cross-device sync or agent-platform integration is included. A Git snapshot may contain sensitive paths or commit subjects; inspect it before exporting or sharing.

## License

MIT. See [LICENSE](LICENSE).
