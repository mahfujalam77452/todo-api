# Todo Workspace - Django REST API

Django REST Framework backend for the Todo Workspace application. It provides JWT authentication, team management, Todo assignment workflows, Scrum lifecycle management, notifications, and administrator analytics.

## Features

- Email/password registration and login
- JWT access and rotating refresh tokens
- Custom `member` and `admin` roles
- Team creation, membership, and team member management
- Todo creation, assignment, acceptance, rejection, priority, categories, and due dates
- Automatic Scrum association for team Todos
- Scrum lifecycle: `created`, `running`, and `ended`
- Server-generated Scrum names: `scrum-1`, `scrum-2`, and so on
- Admin Todo history with Scrum, category, date, and relation filters
- Admin user performance statistics
- 14-day bottleneck reporting
- 90-day completion heatmap
- Six-month team analytics
- Persistent overdue alerts and configurable dashboard thresholds
- Notification events for Todo changes
- OpenAPI documentation and Django admin

## Technology

- Python 3.12+
- Django 5.2
- Django REST Framework
- SimpleJWT
- django-filter
- drf-spectacular
- SQLite for local development
- PostgreSQL support for production
- pytest and factory_boy

Redis is optional. If `REDIS_URL` is empty or omitted, Django uses a local in-memory cache.

## Local setup

The virtual environment is stored in `venv` in this workspace.

```bash
cd todo-api
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set at least `SECRET_KEY` and `ALLOWED_HOSTS` in `.env`. For local development, leave `REDIS_URL` empty to use the local memory cache.

Apply migrations:

```bash
./venv/bin/python manage.py migrate
```

Start the API:

```bash
./venv/bin/python manage.py runserver 127.0.0.1:8000
```

API base URL:

```text
http://127.0.0.1:8000/api
```

Health check:

```text
http://127.0.0.1:8000/api/health
```

Expected response:

```json
{"status":"ok"}
```

## Environment variables

| Variable | Required | Description |
|---|---:|---|
| `SECRET_KEY` | Yes | Django application secret |
| `DEBUG` | No | `true` for local development |
| `ALLOWED_HOSTS` | Production | Comma-separated host names |
| `DATABASE_URL` | Production | PostgreSQL connection URL |
| `REDIS_URL` | No | Redis URL; empty uses in-memory cache |
| `JWT_SIGNING_KEY` | No | Separate JWT key; use at least 32 characters |
| `LOG_FILE` | No | Optional rotating application log |
| `NUM_PROXIES` | No | Trusted reverse proxy count |

With no `DATABASE_URL`, the local database is `db.sqlite3`.

## Demo reset and seed

The demo script removes all existing database data, applies migrations, and creates realistic dashboard data.

```bash
cd todo-api
./reset_and_seed_demo.sh
```

Demo credentials:

| User | Email | Password |
|---|---|---|
| Admin | `demo-admin@example.com` | `@#abcd@#1234@#` |
| General users | `demo-user-1@example.com` through `demo-user-8@example.com` | `@#abcd@#1234@#` |

The script creates multiple teams, active and ended Scrums, categories, completed and open Todos, overdue work, rejected assignments, overloaded users, inactive users, and six-month analytics data.

This command is destructive. It flushes the database before seeding.

## Main API areas

| Area | Endpoints |
|---|---|
| Authentication | `/api/auth/register`, `/api/auth/login`, `/api/auth/token/refresh`, `/api/auth/logout`, `/api/auth/me` |
| Todos | `/api/todos`, `/api/todos/{id}`, `/api/todos/{id}/assign`, `/api/todos/{id}/accept`, `/api/todos/{id}/reject` |
| Teams | `/api/teams`, `/api/admin/teams/{id}` |
| Categories | `/api/categories`, `/api/admin/categories/{id}` |
| Notifications | `/api/notifications`, `/api/notifications/unread-count` |
| Admin users | `/api/admin/users`, `/api/admin/users/{id}` |
| Scrums | `/api/admin/scrums`, `/api/admin/scrums/{id}/start`, `/api/admin/scrums/{id}/end` |
| Dashboard | `/api/admin/dashboard/overview`, `/api/admin/dashboard/history`, `/api/admin/dashboard/teams`, `/api/admin/dashboard/activity` |
| Analytics | `/api/admin/dashboard/heatmap`, `/api/admin/dashboard/teams/{team_id}/analytics` |
| Bottlenecks | `/api/admin/dashboard/bottlenecks/{kind}` |

## Dashboard reporting rules

- Overview and bottleneck statistics use the last 14 days.
- Bottleneck detail pages use the same 14-day scope as overview cards.
- The completion heatmap uses actual `completed_at` dates for the last 90 days.
- Heatmap results include both running and ended Scrum completions.
- Team creation trends use task `created_at` values from the last six months.
- Team velocity uses task `completed_at` values from the last six months.
- Inactive users have no task activity in the last 14 days.
- User performance metrics count work assigned to the selected user.
- User history can include both assigned and created work.

## Documentation

When the server is running:

- Swagger UI: `http://127.0.0.1:8000/api/docs`
- ReDoc: `http://127.0.0.1:8000/api/redoc`
- OpenAPI schema: `http://127.0.0.1:8000/api/schema`

## Tests

Run the complete suite:

```bash
./venv/bin/python -m pytest
```

Run the dashboard integration tests:

```bash
./venv/bin/python -m pytest tests/integration/test_dashboard_api.py -q
```

Check migrations and Django configuration:

```bash
./venv/bin/python manage.py makemigrations --check --dry-run
./venv/bin/python manage.py check
```
