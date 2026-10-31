# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

This is a small workshop scratch directory (not a git repo), with no build system, package manager, linter, or tests. There is nothing to install or build.

- `dev-tracker.html` — the only real code: "DevTrack", a self-contained single-file task/time tracker (HTML + inline CSS + inline vanilla JS, no dependencies). Open it directly in a browser to run it.
- `iiscworkshop.txt` / `iiscWorhshop.md` — exported Claude Code session transcripts (just `/model`, `/effort`, `/export` output); not documentation.
- `1.ai` — empty file.

## Project rules

- **Server**: use only the Python standard library — no third-party packages.
- **Front end**: plain JavaScript in `index.html` — no npm packages or frameworks.
- **Run the app**: `python server.py`
- **Run the tests**: `python test_server.py`
- **Time format**: times always display as `1 h 30 min`.

## DevTrack architecture (`dev-tracker.html`)

- **State**: a single global `S = {tasks: [...]}` persisted to `localStorage` under key `devtrack.v1`. `save()` writes and then calls `render()`; always mutate `S` and call `save()` rather than touching the DOM directly.
- **Rendering**: full re-render via template-string `innerHTML` (no framework). `render()` updates stats, the project filter, and the weekly summary, then dispatches to `renderBoard()` (Kanban columns: todo/doing/review/done, drag-and-drop via `move()`) or `renderTime()` (time-log table) depending on the `view` variable.
- **Task shape**: `title, notes, project, type, status, priority, due, est, link, logs[{date,hours,note}], doneAt`. "Done this week" and weekly summaries are derived from `doneAt` and `logs[].date` compared against `weekStart()` (Monday, ISO date strings compared lexically).
- **Safety conventions**: all user text interpolated into HTML goes through `esc()`; links are only rendered if they match `^https?://`. Inline `onclick="edit('id')"` handlers rely on functions being global.
- Theming is via CSS custom properties on `:root`, with a `prefers-color-scheme: dark` override; status/priority colors are variables (`--todo`, `--doing`, `--high`, ...) that the JS references by name (e.g. `var(--${k})`).
