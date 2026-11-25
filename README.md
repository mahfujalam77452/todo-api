# Todo Workspace - Django REST API

Django REST Framework backend for the Todo Workspace application. It provides JWT authentication, team management, Todo assignment workflows, Scrum lifecycle management, notifications, administrator analytics, **Project Manager (PM) tools** and **background email / PDF reporting** (Celery + Redis).

## Contents

1. [Features](#1-features)
2. [Technology](#2-technology)
3. [Choose how to run it](#3-choose-how-to-run-it)
4. [Local setup (first time)](#4-local-setup-first-time)
5. [Mode A - quick run, no Redis](#5-mode-a---quick-run-no-redis)
6. [Mode B - Redis in Docker + local API, worker and beat](#6-mode-b---redis-in-docker--local-api-worker-and-beat-recommended)
7. [Mode C - everything in Docker Compose](#7-mode-c---everything-in-docker-compose)
8. [Environment variables](#8-environment-variables)
9. [Demo data and demo users](#9-demo-data-and-demo-users)
10. [Roles and Project Manager rules](#10-roles-and-project-manager-rules)
11. [Emails to the Project Manager](#11-emails-to-the-project-manager)
12. [PM bulk email API](#12-pm-bulk-email-api)
13. [Daily PDF team summary](#13-daily-pdf-team-summary)
14. [Tests](#14-tests)
15. [Main API areas](#15-main-api-areas)
16. [Dashboard reporting rules](#16-dashboard-reporting-rules)
17. [Documentation](#17-documentation)
18. [Troubleshooting](#18-troubleshooting)

---

## 1. Features

- Email/password registration and login
- JWT access and rotating refresh tokens
- Roles: `member`, `pm` (Project Manager) and `admin`
- **One Project Manager per team** (enforced by the API)
- Team creation, membership, and team member management
- Todo creation, assignment, acceptance, rejection, priority, categories, and due dates
- Automatic Scrum association for team Todos
- Scrum lifecycle: `created`, `running`, and `ended`
- Server-generated Scrum names: `scrum-1`, `scrum-2`, and so on
- Admin Todo history with Scrum, category, date, and relation filters
- Admin user performance statistics, 14-day bottleneck reporting, 90-day completion heatmap, six-month team analytics
- Persistent overdue alerts and configurable dashboard thresholds
- Notification events for Todo changes
- **Background email**: every team action is emailed to the team's Project Manager
- **PM bulk email**: the PM can email the whole team
- **Nightly PDF summary**: at 00:00 (Asia/Dhaka) each Project Manager receives a PDF summary of their team's previous day
- OpenAPI documentation and Django admin

## 2. Technology

- Python 3.12+
- Django 5.2, Django REST Framework, SimpleJWT, django-filter, drf-spectacular
- Celery 5.7 (background tasks and the nightly schedule) with Redis as the broker
- ReportLab (PDF generation)
- SQLite for local development, PostgreSQL support for production
- pytest and factory_boy

## 3. Choose how to run it

Email sending and the nightly report are **background tasks**. How they run depends on the mode:

| | Mode A: quick | Mode B: Redis in Docker (recommended) | Mode C: all in Docker |
|---|---|---|---|
| Redis | not needed | Docker container | Docker container |
| API | local `runserver` | local `runserver` | container `web` |
| Worker / Beat | not needed (tasks run inside the request) | local terminals | containers `worker` / `beat` |
| Where emails appear | the `runserver` terminal | the **worker** terminal | `docker compose logs worker` |
| Midnight PDF schedule | does **not** run (use the command in section 13) | runs (needs Beat) | runs |
| Best for | quick check of one feature | testing everything as in production | deployment-like test |

The `.env.example` file is prepared for **Mode B**.

## 4. Local setup (first time)

Do this once, whatever mode you choose.

```bash
cd todo-api
python3 -m venv venv                 # skip if venv already exists
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and set at least `SECRET_KEY`. Generate one with:

```bash
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

Apply migrations:

```bash
python manage.py migrate
```

Check that the project is healthy (should print `no issues` and no pending migrations):

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
```

> Every time you pull new code or add a model, run `migrate` again. A missing migration shows up as `no such table: ...` errors.

API base URL: `http://127.0.0.1:8000/api` - health check: `http://127.0.0.1:8000/api/health` (expected `{"status":"ok"}`).

## 5. Mode A - quick run, no Redis

In `.env` set:

```env
REDIS_URL=
CELERY_TASK_ALWAYS_EAGER=true
```

(`CELERY_TASK_ALWAYS_EAGER=true` is the important line: tasks then run immediately inside the request.)

```bash
python manage.py runserver 127.0.0.1:8000
```

Emails are printed in **this** terminal (console email backend, nothing is really sent). Beat and the midnight schedule are not available in this mode.

## 6. Mode B - Redis in Docker + local API, worker and beat (recommended)

### Step 1 - start Redis in Docker

```bash
docker run -d --name todo-redis -p 6379:6379 redis:7-alpine
docker exec todo-redis redis-cli ping        # must answer: PONG
```

Next time: `docker start todo-redis`. Stop it with `docker stop todo-redis`.

### Step 2 - check `.env`

These are the defaults of `.env.example`:

```env
REDIS_URL=redis://localhost:6379/1            # cache and rate limiting (Redis db 1)
CELERY_BROKER_URL=redis://localhost:6379/0    # Celery tasks (Redis db 0)
CELERY_TASK_ALWAYS_EAGER=false                # tasks go to the worker
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

### Step 3 - create demo data

```bash
./reset_and_seed_demo.sh
```

See [section 9](#9-demo-data-and-demo-users). This deletes all data in the database.

### Step 4 - start the three processes (three terminals, venv active in each)

```bash
# Terminal 1 - the API
python manage.py runserver 127.0.0.1:8000

# Terminal 2 - the worker (sends emails, builds PDFs)
celery -A config worker -l info          # on Windows add: -P solo

# Terminal 3 - beat (the clock: fires the nightly summary at 00:00 Asia/Dhaka)
celery -A config beat -l info
```

### Step 5 - make sure everything is connected

- Worker start-up log shows `Connected to redis://...` and lists these tasks:
  `activity.tasks.send_action_email`, `send_bulk_email`, `send_daily_team_summaries`, `send_team_summary`.
- Beat start-up log shows `beat: Starting...`.
- Do an action as a member (section 10) and watch the **worker** terminal print the email.

### How the pieces work together

```text
API (runserver)  --task message-->  Redis  --->  Worker  --> email (console) / PDF
Beat (clock)     --task at 00:00--> Redis  --->  Worker
```

- The API never sends email itself: after the database change is committed it puts a task in Redis.
- The worker takes tasks from Redis and does the slow work (build PDF, send email).
- Beat only creates the nightly task. **Beat without a worker does nothing, and a worker without beat never runs the schedule.** You need both.
- If Redis is down, the API still works (actions succeed) but no email is sent; start Redis and repeat the action.
- **Restart the worker and beat after you change Python code** (they do not reload automatically).
- Beat writes a small `celerybeat-schedule` file in the project folder (ignored by git).

### Test the schedule without waiting for midnight

1. Temporarily edit `config/settings.py`: change `crontab(hour=0, minute=0)` to `crontab(minute="*")` (every minute).
2. Restart beat. Within a minute the worker log shows `send_daily_team_summaries` and one `send_team_summary` per team.
3. A team's summary is sent **once per day**. The next minutes log `already sent`. To send again, delete the record: `python manage.py shell -c "from activity.models import DailySummary; DailySummary.objects.all().delete()"`.
4. **Put `crontab(hour=0, minute=0)` back** when you are done.

## 7. Mode C - everything in Docker Compose

`docker-compose.yml` starts `redis`, `web` (gunicorn on port 8000), `worker` and `beat`.

```bash
docker compose up -d --build
docker compose ps                      # all services should be running / healthy
docker compose logs -f worker          # emails are printed here
```

Create demo data inside the container (replace the password if you want):

```bash
docker compose exec web sh -c "python manage.py flush --noinput \
 && python manage.py seed_demo_dashboard --password '@#abcd@#1234@#' \
 && python manage.py seed_demo_data --password '@#abcd@#1234@#'"
```

Send the PDF summary now and copy the PDFs to your machine:

```bash
docker compose exec worker python manage.py send_daily_summary --force
docker compose cp worker:/data/reports ./reports-from-docker
```

Compose requirements (already set in the provided `docker-compose.yml`):

- `web`, `worker` and `beat` need `CELERY_BROKER_URL: redis://redis:6379/0` - inside a container `localhost` is not Redis, so the `localhost` value from `.env` must be overridden.
- `REPORTS_DIR: /data/reports` keeps a copy of every PDF on the shared volume (Compose runs with `DEBUG=false`, where no copy is saved by default).

Run the tests in a container: `docker compose --profile test run --rm test`.

## 8. Environment variables

| Variable | Required | Description |
|---|---:|---|
| `SECRET_KEY` | Yes | Django application secret |
| `DEBUG` | No | `true` for local development |
| `ALLOWED_HOSTS` | Production | Comma-separated host names |
| `DATABASE_URL` | Production | PostgreSQL connection URL; empty uses SQLite |
| `DB_PATH` | No | SQLite file path (Docker uses `/data/db.sqlite3`) |
| `REDIS_URL` | No | Redis for cache/rate limits; empty uses in-memory cache |
| `CELERY_BROKER_URL` | Mode B/C | Redis URL for Celery tasks; falls back to `REDIS_URL` |
| `CELERY_TASK_ALWAYS_EAGER` | No | `true` = run tasks inside the request (no Redis/worker). Default: `true` only when no broker is set |
| `EMAIL_BACKEND` | No | Default: console backend (prints emails). Use the SMTP backend later to send real email |
| `DEFAULT_FROM_EMAIL` | No | Sender shown in emails |
| `FRONTEND_URL` | No | Base URL for links inside emails (default `http://localhost:3000`) |
| `REPORTS_DIR` | No | Folder where a copy of each PDF summary is saved. Default: `reports/` when `DEBUG=true`, otherwise off |
| `PDF_FONT_PATH`, `PDF_FONT_BOLD_PATH` | No | Optional Unicode `.ttf` fonts for the PDF (see section 13) |
| `JWT_SIGNING_KEY` | No | Separate JWT key; use at least 32 characters |
| `SEED_PASSWORD` | No | Password for `seed_demo_data` when `--password` is not given (required when `DEBUG=false`) |
| `LOG_FILE` | No | Optional rotating application log |
| `NUM_PROXIES` | No | Trusted reverse proxy count |

Real environment variables always win over values in `.env`.

## 9. Demo data and demo users

```bash
./reset_and_seed_demo.sh
```

The script (it works on the local `venv`):

1. applies migrations,
2. **flushes the database (deletes everything)**,
3. runs `seed_demo_dashboard` - admin, teams, Scrums, categories, completed/open/overdue Todos, rejected assignments, overloaded and inactive users, six-month analytics,
4. runs `seed_demo_data` - Project Managers, team members, three days of team activity, notifications, bulk-email history and a running Scrum for every team.

`seed_demo_data` can also run alone, and again and again: it only removes the data it created itself and never touches the Todos made by `seed_demo_dashboard`.

**Password for every demo user:** `@#abcd@#1234@#`

| Email | Name | Role | Team |
|---|---|---|---|
| `demo-admin@example.com` | Demo Admin | **admin** | Engineering |
| `engineering-one@example.com` | Farhan Chowdhury | **pm** | Engineering |
| `engineering-two@example.com` | Rafi Ahmed | member | Engineering |
| `engineering-three@example.com` | Nusrat Jahan | member | Engineering |
| `engineering-four@example.com` | Tanvir Hasan | member | Engineering |
| `design-one@example.com` | Sadia Islam | **pm** | Design |
| `design-two@example.com` | Imran Hossain | member | Design |
| `design-three@example.com` | Maliha Khan | member | Design |
| `marketing-one@example.com` | Kamal Uddin | member | Marketing (**no PM**) |
| `marketing-two@example.com` | Lamia Akter | member | Marketing (**no PM**) |
| `no-team@example.com` | Unassigned User | member | no team |
| `demo-user-1@example.com` ... `demo-user-3@example.com` | Demo User 1-3 | member | Engineering |
| `demo-user-4@example.com` ... `demo-user-6@example.com` | Demo User 4-6 | member | Design |
| `demo-user-7@example.com`, `demo-user-8@example.com` | Demo User 7-8 | member | QA (**no PM**) |

Teams and Scrums: Engineering, Design and QA each have `scrum-1` (ended) and `scrum-2` (running); Marketing has `scrum-1` (running).

What each demo user is good for:

| Use | Log in as |
|---|---|
| Admin pages, change roles, dashboard, Scrums | `demo-admin@example.com` |
| Project Manager tools (Team mail, receives action emails) | `engineering-one@example.com`, `design-one@example.com` |
| Do team actions that email the PM | `engineering-two@`, `engineering-three@`, `engineering-four@` |
| A team with **no PM** (no action emails are sent) | `marketing-one@`, `marketing-two@`, or the QA users |
| User without a team | `no-team@example.com` |

> The Project Manager of Engineering also gets the actions of the `demo-user-1..3` users, because they are Engineering members too.

## 10. Roles and Project Manager rules

| Role | Meaning |
|---|---|
| `member` | Normal user |
| `pm` | Project Manager of **one** team |
| `admin` | Workspace administrator (manages users, roles, teams, Scrums) |

Rules (enforced by `PATCH /api/admin/users/{id}`, answer `409 Conflict` when broken):

- A team can have **only one** Project Manager. Making a second one fails with `Team 'X' already has a Project Manager (Name)`.
- A Project Manager must belong to a team. Assign the team first, then set the role.
- A PM cannot be moved into a team that already has a PM.
- A user has exactly one role, so an admin cannot also be a PM.
- The last admin cannot be demoted, and nobody can change their own role.

## 11. Emails to the Project Manager

When a team member acts, the **PM of that member's team** receives an email with the details. Emails are sent in the background and printed in the console (worker terminal in Mode B/C, `runserver` terminal in Mode A).

| Action | Email subject |
|---|---|
| Todo created (the email also names the assignee when one was given) | `[Team] Name created todo: Title` |
| Todo assigned | `[Team] Name assigned todo: Title` |
| Assignment accepted | `[Team] Name accepted todo: Title` |
| Assignment rejected (includes the reason) | `[Team] Name rejected todo: Title` |
| Todo updated (lists `old -> new` for every changed field) | `[Team] Name updated todo: Title` |
| Todo deleted | `[Team] Name deleted todo: Title` |

No email is sent when:

- the PM did the action himself/herself,
- the team has no PM (Marketing, QA in the demo data),
- an update changes nothing,
- the actor has no team.

Every action is also stored as an `ActivityLog` row (visible in Django admin at `/admin/`) which feeds the PDF summary.

**Try it:** log in as `engineering-two@example.com`, create a Todo and assign it to `engineering-three@example.com`. The email to `engineering-one@example.com` is printed. Then log in as `engineering-three@example.com` and accept / change status / delete. Do the same as `engineering-one@example.com` and see that **no** email is printed.

## 12. PM bulk email API

Only a Project Manager can use it. The team always comes from the PM's own membership, so a PM cannot email another team.

| Method | URL | Purpose |
|---|---|---|
| `POST` | `/api/pm/bulk-emails` | Email every other member of the PM's team |
| `GET` | `/api/pm/bulk-emails` | History of the PM's bulk emails |

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"engineering-one@example.com","password":"@#abcd@#1234@#"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access'])")

curl -X POST http://127.0.0.1:8000/api/pm/bulk-emails \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"subject":"Standup moved","message":"Tomorrow at 10am.\nPlease be on time."}'
```

- Answer `202 Accepted`: the emails are sent in the background. `status` is `sending`, then `sent` (or `partially_failed`).
- Every member gets a **separate** email (nobody sees the other addresses). `Reply-To` is the PM.
- The PM does not receive his/her own bulk email.
- `subject`: 1-150 characters, one line. `message`: 1-5000 characters.
- Errors: `400` invalid input, `403` not a PM, `409` the team has no other member, `429` limit reached (10 bulk emails per hour).
- One bad address does not stop the others; failures are counted in `failed_count`.

## 13. Daily PDF team summary

### What happens

- At **00:00 Asia/Dhaka** Celery Beat starts `send_daily_team_summaries`.
- It creates one job per team that has a Project Manager. The report covers the **day that just ended**.
- Each PM receives an email with the PDF attached (`team-summary-<team>-<date>.pdf`) and a short text summary.
- A team's report for one day is sent only **once** (stored in `DailySummary`), even if beat or the worker repeats the task. Failed sends are retried up to 3 times.
- Teams without a PM get no report.

### What is inside the PDF

1. Banner: team name and date
2. **Highlights**: number of actions, comparison with the day before, most active member, completed and rejected work, overdue and long-unanswered items
3. **The day in numbers**: actions, created, completed, accepted, rejected, deleted
4. **Where the team stands now**: active todos, overdue, awaiting an answer, waiting more than 24 hours
5. **Needs attention**: overdue todos, assignments with no answer for 24 hours, rejections with the reason
6. **Member overview**: actions, completed, active todos and overdue per member
7. **Activity timeline**: every action of the day with time, person and details (first 60 rows)

### Create a report right now (no need to wait for midnight)

```bash
python manage.py send_daily_summary --force            # yesterday (what midnight sends)
python manage.py send_daily_summary --today --force    # today so far
python manage.py send_daily_summary --date 2026-11-23 --force
python manage.py send_daily_summary --team 1 --force   # one team only
```

The command runs in your terminal and needs no worker. `--force` sends again even if it was already sent.

### Where to find the PDF

| How you run | Where |
|---|---|
| Local, `DEBUG=true` | `reports/team-summary-<team>-<date>.pdf` in the project folder |
| Anywhere | set `REPORTS_DIR=/some/folder` in `.env` |
| Docker Compose | `/data/reports` inside the containers: `docker compose cp worker:/data/reports ./reports-from-docker` |
| Email | the console prints the email with the PDF as base64 text. Use the saved file instead. |

Example: after `./reset_and_seed_demo.sh` and `python manage.py send_daily_summary --force` you get `reports/team-summary-engineering-<yesterday>.pdf` and `reports/team-summary-design-<yesterday>.pdf`.

### Notes

- The PDF uses the built-in Helvetica font. Latin text is perfect; characters it cannot draw (for example Bengali) are replaced by `?`. `PDF_FONT_PATH` / `PDF_FONT_BOLD_PATH` can point to a Unicode `.ttf` for other scripts, but the PDF library does not shape Bengali conjunct letters correctly.
- Counts cover the todos that belong to the team.
- Times are shown in Asia/Dhaka.

## 14. Tests

Run the complete suite:

```bash
python -m pytest
```

Useful subsets:

```bash
python -m pytest tests/integration/test_dashboard_api.py -q       # dashboard and Scrum
python -m pytest tests/integration/test_pm_role_api.py -q         # PM role rules
python -m pytest tests/integration/test_bulk_email_api.py -q       # PM bulk email API (mocked)
python -m pytest tests/unit -q
```

`tests/integration/test_bulk_email_api.py` has two mock tests: the Celery task is replaced by a mock, so they need no Redis, no worker and no real email. They check that the API queues the email for the right people and that it queues nothing when the request is refused.

Check migrations and Django configuration:

```bash
python manage.py makemigrations --check --dry-run
python manage.py check
```

In Docker: `docker compose --profile test run --rm test`.

## 15. Main API areas

| Area | Endpoints |
|---|---|
| Authentication | `/api/auth/register`, `/api/auth/login`, `/api/auth/token/refresh`, `/api/auth/logout`, `/api/auth/me` |
| Todos | `/api/todos`, `/api/todos/{id}`, `/api/todos/{id}/assign`, `/api/todos/{id}/accept`, `/api/todos/{id}/reject` |
| Teams | `/api/teams`, `/api/teams/{id}/members`, `/api/admin/teams/{id}` |
| Categories | `/api/categories`, `/api/admin/categories/{id}` |
| Notifications | `/api/notifications`, `/api/notifications/unread-count` |
| Admin users (roles, PM) | `/api/admin/users`, `/api/admin/users/{id}` |
| **Project Manager** | `/api/pm/bulk-emails` |
| Scrums | `/api/admin/scrums`, `/api/admin/scrums/{id}/start`, `/api/admin/scrums/{id}/end` |
| Dashboard | `/api/admin/dashboard/overview`, `/api/admin/dashboard/history`, `/api/admin/dashboard/teams`, `/api/admin/dashboard/activity` |
| Analytics | `/api/admin/dashboard/heatmap`, `/api/admin/dashboard/teams/{team_id}/analytics` |
| Bottlenecks | `/api/admin/dashboard/bottlenecks/{kind}` |

## 16. Dashboard reporting rules

- Overview and bottleneck statistics use the last 14 days.
- Bottleneck detail pages use the same 14-day scope as overview cards.
- The completion heatmap uses actual `completed_at` dates for the last 90 days.
- Heatmap results include both running and ended Scrum completions.
- Team creation trends use task `created_at` values from the last six months.
- Team velocity uses task `completed_at` values from the last six months.
- Inactive users have no task activity in the last 14 days.
- User performance metrics count work assigned to the selected user.
- User history can include both assigned and created work.
- A finished (`ended`) Scrum cannot be started again.

## 17. Documentation

When the server is running:

- Swagger UI: `http://127.0.0.1:8000/api/docs`
- ReDoc: `http://127.0.0.1:8000/api/redoc`
- OpenAPI schema: `http://127.0.0.1:8000/api/schema`
- Django admin: `http://127.0.0.1:8000/admin/` (Activity logs, Bulk emails and Daily summaries are visible here)

## 18. Troubleshooting

| Problem | Cause and fix |
|---|---|
| No email is printed after an action | Mode B/C: the **worker** is not running or not connected to Redis; start it and watch its terminal. Mode A: set `CELERY_TASK_ALWAYS_EAGER=true`. Also check that the actor's team has a PM and that the actor is not that PM. |
| `Connection refused` to `localhost:6379` | Redis is not running: `docker start todo-redis` (or run the `docker run` command in section 6). The API still works, only emails are not queued. |
| `REDIS_URL=` is empty but emails still do not appear | `.env` has `CELERY_BROKER_URL` and `CELERY_TASK_ALWAYS_EAGER=false`. Set `CELERY_TASK_ALWAYS_EAGER=true`. |
| Worker/Beat ignore my code change | They do not auto-reload. Stop (`Ctrl+C`) and start them again. |
| Beat is running but no report arrives at midnight | A worker must be running too. Check the beat log for `Sending due task daily-team-summary`, then the worker log. |
| `send_daily_summary` prints `No team has a Project Manager` | No user has role `pm`. Run `./reset_and_seed_demo.sh`, or make a team member a PM in the admin Users page. |
| `send_daily_summary` prints `already sent` | That team/day was sent before. Add `--force`. |
| `no such table: activity_...` | Run `python manage.py makemigrations activity` and `python manage.py migrate`. |
| `Team ... already has a Project Manager` (409) | Expected: change the other PM's role first. |
| The PDF is not in `reports/` | `REPORTS_DIR` is off when `DEBUG=false`. Set `REPORTS_DIR=reports` in `.env`. |
| Docker: worker cannot reach Redis | `CELERY_BROKER_URL` must be `redis://redis:6379/0` inside Compose (see section 7). |
| Seed command asks for a password | Pass `--password` or set `SEED_PASSWORD` (required when `DEBUG=false`). |