---
name: standup
description: Write a three-line daily standup (Yesterday, Today, Blockers) from data/tasks.json and the git log since yesterday, saved to data/standup.md. Use when the user asks for a standup, daily update, or "what did I do yesterday".
---

# Standup

Write a short standup to `data/standup.md` from the task list and recent commits.

## Steps

1. Read `data/tasks.json`. If it is missing or invalid JSON, say so, carry on with the git log alone, and leave a note under the relevant line.
2. Get yesterday's work from git: `git log --since=yesterday --pretty=format:"%h %s"`. If this is not a git repository, or the log is empty, say so in the reply and use the tasks only.
3. Build three lines:
   - **Yesterday:** what was finished. Use tasks completed yesterday or marked done, plus the commit subjects. Merge items that describe the same work.
   - **Today:** what is planned. Use tasks that are in progress or due today, most urgent first.
   - **Blockers:** tasks marked blocked, or anything stuck that the data shows. Write `None` if there is nothing.
4. Write `data/standup.md` (create `data/` if needed, overwrite the existing file) with exactly these three lines and nothing else:

```
Yesterday: ...
Today: ...
Blockers: ...
```

5. Reply with the three lines and say where the file was saved.

## Rules

- Each line is one line: items separated by semicolons, no bullets, no line breaks.
- Use only what is in the data. Do not invent tasks, commits, or blockers. If a field's meaning is unclear, work it out from the data and don't ask.
- Show any times in the project format, `1 h 30 min`.
- Never include secrets, tokens, or email addresses that appear in commit messages or task notes.
