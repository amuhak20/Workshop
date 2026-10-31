# Test Plan: DevTrack (`dev-tracker.html`)

Single-file task and time tracker. Plain JS, state in `localStorage` key `devtrack.v1`, no server, no build. All testing is manual in a browser unless noted.

## 1. Scope
**In scope:** task create/edit/delete, Kanban board and drag-and-drop, filters and search, time logging, Time log view, stats, weekly summary, export/import, persistence, theming, responsive layout, input safety.
**Out of scope:** multi-user sync, server behaviour, browsers older than the last 2 major versions of Chrome, Edge, Firefox, Safari.

## 2. Environment
- Open the file directly (`file://`) and via a static server (`python -m http.server`) to confirm `localStorage` works in both.
- Browsers: Chrome, Edge, Firefox, Safari (drag-and-drop and `<dialog>` differ most).
- Viewports: 1440 px, 768 px, 375 px. OS light and dark mode.
- Reset between runs: DevTools > Application > Local Storage > delete `devtrack.v1`.
- Use a throwaway browser profile for the private-window and blocked-storage cases.

## 3. Test data
| Set | Contents |
|---|---|
| Empty | no `devtrack.v1` key |
| Small | 6 tasks across 3 projects, all 4 statuses, all 3 priorities, 2 types |
| Edge | title of 200 chars; title/notes with `<script>`, `"`, `'`, `&`; link `javascript:alert(1)`; link `https://x.test`; est 0.25; due yesterday, today, tomorrow |
| Large | 500 tasks, 2000 log entries (generate via console) |
| Corrupt | `devtrack.v1` = `{bad json`, `null`, `[]`, `{"tasks":"x"}` |

## 4. Test cases
Priority: **P1** must pass to release, **P2** should pass, **P3** nice to have.

### 4.1 Task create / edit / delete
| ID | P | Steps | Expected |
|---|---|---|---|
| T-01 | P1 | Click **+ New task**, leave title empty, Save | Browser blocks submit (title required). No task added. |
| T-02 | P1 | Create task with title only | Card appears in **To do**, priority medium, `⏱ 0.0h`, no tag, no due date. Dialog closes. |
| T-03 | P1 | Create task with all fields filled | Card shows project tag, type, due date, `⏱ 0.0/<est>h`, "link ↗". |
| T-04 | P1 | Edit a task: change title, project, type, priority, due, est, notes | Card updates immediately; reload keeps changes. |
| T-05 | P1 | Edit a task and press Cancel | No change. Dialog closes. |
| T-06 | P1 | Delete: confirm OK | Task removed, counts update. |
| T-07 | P2 | Delete: confirm Cancel | Task stays; edit dialog stays open. |
| T-08 | P2 | Open **+ New task** after editing another task | Form is blank (defaults), title "New task", Delete button hidden. |
| T-09 | P2 | Clear est on a task that had one | Est saved as 0; card shows `⏱ x.xh` with no `/est`. |
| T-10 | P3 | Press Esc in the dialog | Dialog closes, no save. |

### 4.2 Status and drag-and-drop
| ID | P | Steps | Expected |
|---|---|---|---|
| S-01 | P1 | Drag a card to another column | Card moves, column counts update, persists after reload. |
| S-02 | P1 | Drag a card to **Done** | `doneAt` = today; stat "Done this week" +1; task listed in Weekly summary. |
| S-03 | P1 | Drag a Done card back to **Doing** | `doneAt` cleared; stat and summary list drop it. |
| S-04 | P2 | Change status via the edit form to Done and back | Same effect as S-02/S-03. |
| S-05 | P2 | Drag and drop a card on its own column | No change, no error. |
| S-06 | P2 | Drag over a column, then away | Dashed outline appears then clears. (Known gap to check: outline after a successful drop.) |
| S-07 | P2 | Task with a past due date moved to Done | Date stops showing as overdue; Overdue stat decrements. |

### 4.3 Filters and search
| ID | P | Steps | Expected |
|---|---|---|---|
| F-01 | P1 | Type in search | Board filters live by title, notes and project, case-insensitive. |
| F-02 | P1 | Pick a project | Only that project's tasks show; empty columns show "—". |
| F-03 | P1 | Pick a type | Only that type shows. |
| F-04 | P2 | Combine search + project + type | Intersection (AND). |
| F-05 | P2 | Select project, then delete or rename its last task | Dropdown falls back to a valid value; no stale selection hiding everything. |
| F-06 | P2 | New project name entered in the dialog | Appears in the project filter and in the datalist suggestions. |
| F-07 | P3 | Search with regex characters `(`, `[`, `.*` | Treated as plain text, no error. |

### 4.4 Time logging
| ID | P | Steps | Expected |
|---|---|---|---|
| L-01 | P1 | **+ Time** on a task, defaults (1 h, today), Log | Card hours +1.0; stat "Logged this week" +1.0h. |
| L-02 | P1 | Log 0.25 h | Card shows 0.3h (rounded to 1 decimal) while the stored value is 0.25. |
| L-03 | P1 | Log 0 or negative hours | Blocked by `min=0.25`. |
| L-04 | P1 | Log with a date from last week | Appears in Time log; excluded from "Logged this week" and weekly summary. |
| L-05 | P2 | Log with a note | Note shown in Time log table. |
| L-06 | P2 | Cancel the Log dialog | Nothing logged. |
| L-07 | P2 | Log time on two projects | Time log shows per-project totals as tags; weekly summary matches. |
| L-08 | P2 | Open Log dialog, cancel, open on another task | Dialog shows the correct task name and reset defaults. |
| L-09 | P3 | Log hours with many decimals (`1.333`) | Step validation blocks or rounds sensibly. |

### 4.5 Views, stats and weekly summary
| ID | P | Steps | Expected |
|---|---|---|---|
| V-01 | P1 | Toggle Board / Time log | Correct section visible; active tab highlighted; filters still apply to Board. |
| V-02 | P1 | Empty state | Stats all 0; Time log shows the "No time logged yet" message; weekly summary shows "No time logged this week." |
| V-03 | P1 | Stats correctness with Small set | Open = tasks not Done; In progress = status doing; Overdue = due < today and not Done; Done this week and Logged this week match the data. |
| V-04 | P1 | **Week boundary:** logs dated Sunday and the following Monday | Week starts Monday; Sunday belongs to the previous week. |
| V-05 | P1 | **Timezone:** set the OS or browser timezone to UTC+13 and UTC-11, then check around local midnight | `today()` and `weekStart()` use `toISOString()` (UTC). Expect a possible one-day error in "today", overdue and week start. Record result; likely defect. |
| V-06 | P2 | Time log ordering | Newest date first. |
| V-07 | P2 | Overdue styling | Past due and not Done shows red/bold date; today and future do not. |

### 4.6 Export / Import / persistence
| ID | P | Steps | Expected |
|---|---|---|---|
| P-01 | P1 | Add tasks, reload | Everything persists. |
| P-02 | P1 | Export | Downloads `devtrack-YYYY-MM-DD.json` containing `tasks` with logs. |
| P-03 | P1 | Clear storage, Import the exported file, confirm | Data restored identical; confirm dialog shown first. |
| P-04 | P1 | Import: confirm Cancel | Existing data unchanged. |
| P-05 | P1 | Import invalid files: non-JSON, `{}`, `{"tasks":"x"}`, wrong extension | "Invalid DevTrack file." alert; data unchanged. |
| P-06 | P2 | Import the same file twice | Allowed; replaces, no duplicates. |
| P-07 | P2 | Corrupt `devtrack.v1` values (see Corrupt set), reload | App loads with an empty board, no uncaught exception. |
| P-08 | P2 | Private window or blocked storage | App works for the session; changes do not persist; no crash. |
| P-09 | P2 | Open in two tabs, edit in one, then the other | Document the behaviour (last write wins; the other tab is stale until reload). |
| P-10 | P3 | Import a file with tasks missing optional fields (`logs`, `due`, `notes`) | Renders without errors; `notes`-less search does not break. |

### 4.7 Security and robustness
| ID | P | Steps | Expected |
|---|---|---|---|
| X-01 | P1 | Title, project, notes containing `<img src=x onerror=alert(1)>` and `"><script>` | Shown as literal text everywhere (cards, Time log, weekly summary, project filter, datalist). No script runs. |
| X-02 | P1 | Link `javascript:alert(1)` | No "link ↗" rendered (only `http(s)` allowed). |
| X-03 | P1 | Link `https://x.test/?a=1&b="2"` | Link renders and opens in a new tab with `rel="noopener"`. |
| X-04 | P1 | **Import a file whose task `id` is `x');alert(1);//`** | `id` is placed unescaped in `onclick="edit('…')"` and `data-id`. Expect script execution = defect. Verify and report. |
| X-05 | P2 | Import a log with `hours` as a string or null | Stats show a number, not `NaN`. Likely defect. |
| X-06 | P2 | Import tasks with an unknown `status` | Task is hidden from the board but counted in Open. Document or fix. |
| X-07 | P2 | Very long title (200+ chars, no spaces) | Card does not overflow the column. |

### 4.8 UI, accessibility, compatibility
| ID | P | Steps | Expected |
|---|---|---|---|
| U-01 | P1 | Layout at 1440 / 768 / 375 px | Columns reflow; no horizontal page scroll; dialogs fit (`min(480px,92vw)`). |
| U-02 | P1 | Dark mode | All text and borders readable; priority bars and status colours visible. |
| U-03 | P2 | Keyboard only | Can reach New task, Edit, + Time, tabs, dialog fields; Enter submits, Esc closes. Note: cards are drag-only, so there is no keyboard way to change status except via Edit. |
| U-04 | P2 | Screen reader pass | Buttons have text names; the dialog is announced. Note missing labels linking if any. |
| U-05 | P2 | Touch device | Drag-and-drop with the HTML5 API generally does not work on touch; confirm the Edit dialog status field is a usable fallback. |
| U-06 | P3 | Performance with the Large set | Initial render and each interaction under ~300 ms; the full re-render on every `save()` is the likely bottleneck. |

## 5. Known risks to check first
1. **UTC vs local dates** in `today()` / `weekStart()` (V-05).
2. **Unescaped `id`** in inline handlers and `data-id` on imported data (X-04).
3. **No schema validation on import** beyond `Array.isArray(d.tasks)` (P-10, X-05, X-06).
4. **Drag-and-drop only** status change; poor touch and keyboard support (U-03, U-05).
5. Full `innerHTML` re-render on every change: focus and scroll loss, performance (U-06).

## 6. Entry and exit criteria
- **Entry:** latest `dev-tracker.html` build; test browsers available; data sets prepared.
- **Exit:** all P1 pass; no open P1/P2 defects without an agreed workaround; every defect from section 5 either fixed or logged with severity.

## 7. Reporting
Record per case: ID, browser/OS, pass/fail, defect link or note, screenshot for UI failures. Log defects with steps, expected vs actual, severity (S1 data loss or script execution, S2 wrong numbers, S3 cosmetic).

## 8. Suggested automation (later)
Playwright for the P1 flows (T, S, L, P, X-01/02). Seed state by writing `devtrack.v1` before page load; use a fixed clock (`page.clock`) for the V-04/V-05 date cases.
