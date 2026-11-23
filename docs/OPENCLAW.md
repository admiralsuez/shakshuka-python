# OpenClaw integration — control Shakshuka tasks from your bot

Shakshuka exposes a local REST API with **no authentication** (it binds to
`127.0.0.1:8989` by default, so nothing outside the machine can reach it).
Any agent that can run shell commands — OpenClaw or similar — can add, edit,
complete, list and delete tasks with plain `curl` calls.

A ready-made skill file ships with this repo at
[`integrations/openclaw/SKILL.md`](../integrations/openclaw/SKILL.md) — copy
it to `~/.openclaw/workspace/skills/shakshuka/SKILL.md` and restart OpenClaw.

The Flask app must be running (`shakshuka` / the tray app) — the API lives
inside it. Port can be overridden with the `SHAKSHUKA_PORT` env var.

## API endpoints (src/routes/task_routes.py)

| Action | Method + path | Body |
|---|---|---|
| View all tasks | `GET /api/tasks` | — |
| Add task | `POST /api/tasks` | `{"title": "...", "priority": "medium", "project": "", "description": ""}` |
| Edit task (partial) | `PATCH /api/tasks/<id>` | any subset of fields |
| Replace task | `PUT /api/tasks/<id>` | full task JSON |
| Complete task | `POST /api/tasks/<id>/complete` | — |
| Strike task | `POST /api/tasks/<id>/strike` | `{"type": "..."}` |
| Delete task | `DELETE /api/tasks/<id>` | — |
| Archive / unarchive | `POST /api/tasks/<id>/archive` / `/unarchive` | — |
| Schedule | `POST /api/tasks/<id>/schedule` | `{"hour": "22:30", "duration": 30, "date": "YYYY-MM-DD"}` |
| View archived | `GET /api/tasks/archived` | — |

Returns: `201` + task JSON on create (409 if a task with the same title+project
exists), task JSON on success, `{"error": "..."}` otherwise.

Quick test from the server:

```bash
curl -s http://127.0.0.1:8989/api/tasks
curl -s -X POST http://127.0.0.1:8989/api/tasks \
  -H 'Content-Type: application/json' \
  -d '{"title": "Water the plants", "priority": "low"}'
```

## OpenClaw skill setup

Copy the SKILL.md below into `~/.openclaw/workspace/skills/shakshuka/SKILL.md`
on the server. OpenClaw loads workspace skills automatically; after that the
agent can answer things like "add a task to call mom tomorrow" or "what's on
my task list?" by running the curl commands itself.

```markdown
---
name: shakshuka
description: Manage tasks in the local Shakshuka task manager (add, edit, complete, list, delete tasks) via its localhost REST API. Use whenever the user mentions tasks, to-dos, or reminders for their Shakshuka app.
---

# Shakshuka task API

Base URL: http://127.0.0.1:8989 — no auth needed. (If you reached the app via
Tailscale instead of a tunnel, replace the base URL with the app's tailnet
address.) Always pass `Content-Type: application/json` on POST/PATCH/PUT bodies.

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
- If curl fails to connect, Shakshuka is not running — tell the user to start it.
- Priority must be one of: low, medium, high.
- Never delete or archive without confirming with the user.
```

## If OpenClaw runs on a *different* machine

### Same home/office network (LAN) — simplest remote setup

1. Make the app listen on the network (it may already — check first with
   `netstat -ano | findstr :8989` on Windows; `0.0.0.0:8989` means done).
   If needed, set the `SHAKSHUKA_HOST` environment variable to `0.0.0.0`
   (or create a `.env` file next to `main.py` with `SHAKSHUKA_HOST=0.0.0.0`)
   and restart the app.
2. Allow inbound TCP 8989 in Windows Firewall, private profile only:
   ```powershell
   netsh advfirewall firewall add rule name="Shakshuka API" dir=in action=allow protocol=TCP localport=8989 profile=private
   ```
3. Find the app machine's LAN IP (`ipconfig` on Windows → IPv4 address,
   e.g. `192.168.1.13`) and reserve it in your router's DHCP settings so it
   doesn't change.
4. From the bot machine, verify: `curl http://192.168.1.13:8989/health`
5. In the skill file, replace `127.0.0.1` with the LAN IP
   (`sed -i 's/127\.0\.0\.1:8989/192.168.1.13:8989/g' ~/.openclaw/workspace/skills/shakshuka/SKILL.md`)
   and restart OpenClaw.

Caveats: the API is unauthenticated — this is acceptable **only** inside a
private network you control; never add a router port-forward for 8989. The
bot loses access when the app machine sleeps or the app isn't running, so
set Sleep = Never and enable app autostart.

### App on Windows, bot on a remote Linux server

The Windows app binds `127.0.0.1` (per your `.env`) and is behind home NAT,
so the connection must be initiated *from Windows*. Two good options:

#### Option W1 — reverse SSH tunnel from Windows (recommended, zero installs)

Windows 10/11 ships an SSH client. One-time setup:

```powershell
# On Windows: create a key and copy the public key to the bot server
ssh-keygen -t ed25519
type $env:USERPROFILE\.ssh\id_ed25519.pub   # paste into the bot server's
#   /home/<tunneluser>/.ssh/authorized_keys, prefixed with:
#   restrict,port-forwarding,permitopen="127.0.0.1:8989"
```

Keepalive script — save as `%USERPROFILE%\shakshuka-tunnel.bat`:

```bat
@echo off
:loop
ssh -N -R 127.0.0.1:8989:127.0.0.1:8989 ^
    -o ServerAliveInterval=30 -o ServerAliveCountMax=3 ^
    -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=accept-new ^
    tunneluser@your-bot-server
timeout /t 5 /nobreak
goto loop
```

Start it at login: `Win+R` → `shell:startup` → shortcut to the .bat (or use
Task Scheduler). Now on the Linux bot server, `http://127.0.0.1:8989` IS the
Windows app — **the skill above works unchanged**, full CRUD included.

Notes:
- sshd's default `GatewayPorts no` keeps the tunnel loopback-only on the bot
  server, so the unauthenticated API stays private to that machine.
- When the Windows app/PC is off, the bot's calls fail to connect — it will
  just tell the user Shakshuka isn't running. Restarting the app re-connects
  automatically (the loop retries).

#### Option W2 — Tailscale on both machines

Install Tailscale on Windows + the bot server, keep the app bound to
`0.0.0.0` (default) or the tailnet IP, allow inbound TCP 8989 in Windows
Defender Firewall (scope it to the Tailscale subnet). The bot then uses
`http://<windows-tailscale-ip>:8989` as the base URL in the skill. Simplest
if you don't want to babysit a tunnel, still private (tailnet-only).

For app-level auth on top of either option, see Option C below.

### Other topologies

The task API has **no authentication**, so never expose port 8989 directly to
the internet. Pick one of these:

### Option A — SSH tunnel (recommended, zero code changes)

Keep the app bound to `127.0.0.1` and run a persistent tunnel on the bot's
machine so `localhost:8989` there maps to the server:

```bash
# one-off
ssh -N -L 8989:127.0.0.1:8989 your-server

# persistent (autossh as a systemd service on the bot machine)
sudo apt install autossh
sudo systemctl enable --now autossh-shakshuka@your-server
```

Point the skill's base URL at `http://127.0.0.1:8989` on the bot machine —
the full CRUD API from the table above works unchanged.

### Option B — private VPN (Tailscale/WireGuard)

Install Tailscale on both machines and set the app's bind host to the
tailnet interface (it defaults to `0.0.0.0`, override with the
`SHAKSHUKA_HOST` env var, see `src/constants.py`):

```bash
SHAKSHUKA_HOST=100.x.y.z shakshuka     # or keep 0.0.0.0 inside the tailnet
```

The bot then calls `http://<server-tailscale-ip>:8989/api/tasks` directly.
Only do this inside a private network — there is still no app-level auth.

### Option C — built-in mobile pairing API (token-authenticated)

Shakshuka ships a Bearer-token API designed for phones
(`src/routes/mobile_routes.py`, prefix `/api/mobile`). Useful when you want
app-level auth, but note its write path is *approval-based* (bot submits,
you approve on the desktop):

```bash
# 1. On the server (must be local/tunneled), generate a pairing code:
curl -s http://127.0.0.1:8989/api/mobile/pairing
#    -> {"code": "123456", "expires_in": 300, ...}

# 2. Pair the bot (can run from anywhere):
curl -s -X POST http://<server>:8989/api/mobile/pair \
  -H 'Content-Type: application/json' \
  -d '{"code": "123456", "device_id": "openclaw-bot", "device_name": "OpenClaw"}'
#    -> {"token": "..."}

# 3. Use the token:
curl -s http://<server>:8989/api/mobile/current-tasks \
  -H 'Authorization: Bearer <token>'                       # view tasks
curl -s -X POST http://<server>:8989/api/mobile/inbox \
  -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' \
  -d '{"type": "task", "title": "..."}'                    # submit (needs approval)
```

Endpoints: `/current-tasks` (read-only view), `/inbox` → `/inbox/pending` →
`/inbox/<id>/approve|reject` (task suggestions), `/notes` (read/write notes).
For full unattended add/edit/complete, use Option A or B.
