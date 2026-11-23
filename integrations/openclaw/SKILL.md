---
name: shakshuka
description: Manage tasks in the local Shakshuka task manager (add, edit, complete, list, delete tasks) via its localhost REST API. Use whenever the user mentions tasks, to-dos, or reminders for their Shakshuka app.
---

# Shakshuka task API

Base URL: http://127.0.0.1:8989 — no auth needed. Always pass
`Content-Type: application/json` on POST/PATCH/PUT bodies.

> If your bot runs on a DIFFERENT machine than the Shakshuka app, replace
> `127.0.0.1` with the app machine's LAN IP (e.g. `http://192.168.1.13:8989`).
> See docs/OPENCLAW.md in the Shakshuka repository for all setup options.

## List tasks
    curl -s http://127.0.0.1:8989/api/tasks

Response is a JSON array; each task has `id`, `title`, `completed`,
`priority`, `project`, `description`, `due_date`.

## Add a task
    curl -s -X POST http://127.0.0.1:8989/api/tasks \
      -H 'Content-Type: application/json' \
      -d '{"title": "<title>", "priority": "<low|medium|high>"}'

409 means a task with the same title already exists — tell the user.

## Complete a task
Find the `id` from the list first, then:
    curl -s -X POST http://127.0.0.1:8989/api/tasks/<id>/complete

## Edit a task
    curl -s -X PATCH http://127.0.0.1:8989/api/tasks/<id> \
      -H 'Content-Type: application/json' \
      -d '{"title": "<new title>"}'

## Delete a task (confirm with the user first)
    curl -s -X DELETE http://127.0.0.1:8989/api/tasks/<id>

## Notes
- If curl fails to connect, Shakshuka is not running (or the machine is
  asleep) — tell the user to start it / wake it up.
- Priority must be one of: low, medium, high.
- Never delete or archive without confirming with the user.
