# TODO List REST API

A secure TODO management API built with Django and Django REST Framework.
Users authenticate with email-based JWT tokens and can access only their own
todos. Categories are global, readable by authenticated users, and writable
only by administrators.

## Features

- Email-based custom user model
- JWT access/refresh tokens with refresh-token blacklist logout
- Private per-user TODOs
- Categories with case-insensitive unique names
- Partial updates with `PATCH`; `PUT` is intentionally disabled
- Filtering, search, ordering, and limit/offset pagination
- Due date, priority, overdue, and category filters
- Redis-backed category caching and throttling when Redis is configured
- Consistent JSON errors
- OpenAPI schema, Swagger UI, and ReDoc
- Django admin customization
- Unit and API integration tests

## Technology

- Python 3.12+
- Django 5.2
- Django REST Framework
- SQLite
- Redis (optional for local development, recommended for production)
- SimpleJWT
- django-filter
- drf-spectacular
- pytest-django, factory_boy, freezegun, coverage

## Quick start

### 1. Clone the repository

```bash
git clone https://github.com/mahfujalam77452/todo-api.git
cd todo-api
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate
```

On Windows PowerShell:

```powershell
venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Generate a secret key:

```bash
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

Put the generated value in `.env` as `SECRET_KEY`. Never commit `.env`.

### 5. Apply migrations

```bash
python manage.py migrate
```

### 6. Create an admin user

```bash
python manage.py createsuperuser
```

The command asks for an email address, name, and password.

### 7. Start the development server

```bash
python manage.py runserver
```

The API is available at `http://127.0.0.1:8000`.

## API documentation

Start the server and open:

- Swagger UI: `http://127.0.0.1:8000/api/docs`

- OpenAPI JSON/YAML response: `http://127.0.0.1:8000/api/schema`

### Deployed API

The live API is available at:

```text
https://todo-api-awz4.onrender.com
```

Open the following URLs in a browser:

- Swagger UI: https://todo-api-awz4.onrender.com/api/docs

- OpenAPI schema: https://todo-api-awz4.onrender.com/api/schema
- Health check: https://todo-api-awz4.onrender.com/api/health

The health endpoint should return:

```json
{"status": "ok"}
```

You can also check it from a terminal:

```bash
curl https://todo-api-awz4.onrender.com/api/health
```

## Environment variables

| Variable | Required | Description |
|---|---:|---|
| `SECRET_KEY` | Yes | Django secret key |
| `DEBUG` | No | `true` for local development; use `false` in production |
| `ALLOWED_HOSTS` | Production | Comma-separated allowed hosts |
| `LOG_FILE` | No | Optional rotating log file path |
| `REDIS_URL` | No | Redis URL, for example `redis://localhost:6379/1` |
| `JWT_SIGNING_KEY` | No | Separate JWT signing key; must be at least 32 characters |
| `NUM_PROXIES` | No | Number of trusted reverse proxies used for client IP throttling |

If `REDIS_URL` is empty, the project uses per-process in-memory cache. The API
continues to work, but cache and throttle state is not shared between workers.

## Redis setup

Redis is optional for a single-process development server.

With Redis running locally:

```bash
redis-server
```

Set this in `.env`:

```dotenv
REDIS_URL=redis://localhost:6379/1
```

Redis is recommended for multiple workers because category cache and rate-limit
counters then use one shared store. If Redis becomes unavailable, caching and
throttling fail open; the API itself remains available.

## Docker

Docker Compose starts the Django web service and Redis together. The SQLite
database and Redis append-only data use named volumes, so container restarts do
not remove application data.

Create `.env` first and set a real `SECRET_KEY`:

```bash
cp .env.example .env
```

Then build and start:

```bash
docker compose up --build -d
```

If your secret contains `$` and Compose prints interpolation warnings, run the
same command with automatic `.env` interpolation disabled. The explicit
`env_file` entry still loads `.env` as raw values:

```bash
COMPOSE_DISABLE_ENV_FILE=1 docker compose up --build -d
```

Check service status and logs:

```bash
docker compose ps
docker compose logs -f web
```

The web container automatically runs migrations and `collectstatic` before
Gunicorn starts. Verify the healthcheck:

```bash
curl http://127.0.0.1:8000/api/health
```

Expected response:

```json
{"status": "ok"}
```

Create an admin user inside the web container:

```bash
docker compose exec web python manage.py createsuperuser
```

Stop the services without deleting named volumes:

```bash
docker compose down
```

To remove the database and Redis data as well, use this destructive command:

```bash
docker compose down -v
```

The image runs as a non-root `app` user. The SQLite volume is mounted at
`/data/db.sqlite3`, and Redis is available to Django at
`redis://redis:6379/1`.

### Run tests inside Docker

The production `web` image excludes the test source files. Compose provides a
separate `test` profile that mounts the repository read-only and runs the same
pytest suite inside the container:

```bash
docker compose --profile test run --rm test
```

Run only unit tests:

```bash
docker compose --profile test run --rm test pytest tests/unit
```

Run only integration tests:

```bash
docker compose --profile test run --rm test pytest tests/integration
```

The test service uses an isolated temporary SQLite database and in-memory
cache, so it does not modify the development database or depend on a locally
running Redis.



The committed schema is [schema.yml](./schema.yml). Validate or regenerate it:

```bash
python manage.py spectacular --file schema.yml --validate
```

In Swagger UI, click **Authorize** and enter:

```text
Bearer <access-token>
```

## Authentication flow

### Register

```bash
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Alice",
    "email": "alice@example.com",
    "password": "A-safe-password-123!"
  }'
```

### Login

```bash
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@example.com",
    "password": "A-safe-password-123!"
  }'
```

The response contains `access`, `refresh`, and `user`. Use the access token:

```bash
curl http://127.0.0.1:8000/api/todos \
  -H "Authorization: Bearer <access-token>"
```

### Refresh

```bash
curl -X POST http://127.0.0.1:8000/api/auth/token/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh": "<refresh-token>"}'
```

### Logout

```bash
curl -i -X POST http://127.0.0.1:8000/api/auth/logout \
  -H "Content-Type: application/json" \
  -d '{"refresh": "<refresh-token>"}'
```

Logout blacklists the refresh token and returns `204 No Content`.

## Endpoint summary

| Method | Endpoint | Authentication | Description |
|---|---|---|---|
| `GET` | `/api/health` | Public | Liveness check |
| `POST` | `/api/auth/register` | Public | Register with email |
| `POST` | `/api/auth/login` | Public | Obtain access/refresh tokens |
| `POST` | `/api/auth/token/refresh` | Public | Rotate refresh token |
| `POST` | `/api/auth/logout` | Public with refresh token | Blacklist refresh token |
| `GET` | `/api/todos` | Authenticated | List own todos |
| `POST` | `/api/todos` | Authenticated | Create a todo |
| `GET` | `/api/todos/{id}` | Authenticated | Retrieve own todo |
| `PATCH` | `/api/todos/{id}` | Authenticated | Partially update own todo |
| `DELETE` | `/api/todos/{id}` | Authenticated | Hard-delete own todo |
| `GET` | `/api/categories` | Authenticated | List categories |
| `GET` | `/api/categories/{id}` | Authenticated | Retrieve a category |
| `POST` | `/api/categories` | Admin | Create a category |
| `PATCH` | `/api/categories/{id}` | Admin | Update a category |
| `DELETE` | `/api/categories/{id}` | Admin | Delete a category |

`PUT` is disabled for TODOs and categories and returns `405 Method Not Allowed`.

## Todo examples

### Create

```bash
curl -X POST http://127.0.0.1:8000/api/todos \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Buy groceries",
    "description": "Milk and rice",
    "priority": 3,
    "due_date": "2026-12-01T18:00:00+06:00"
  }'
```

### Partial update

```bash
curl -X PATCH http://127.0.0.1:8000/api/todos/1 \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{"is_completed": true}'
```

### List, filter, search, order, and paginate

```text
GET /api/todos?limit=10&offset=0
GET /api/todos?status=pending
GET /api/todos?priority=3&overdue=true
GET /api/todos?has_category=true
GET /api/todos?search=groceries
GET /api/todos?ordering=-created_at
```

List responses use:

```json
{
  "count": 1,
  "limit": 10,
  "offset": 0,
  "next": null,
  "previous": null,
  "results": []
}
```

## Category management

Any authenticated user can read categories. Only an active staff user with the
corresponding Django model permission can create, update, or delete them.
Superusers have all permissions.

Create a category through the admin panel:

1. Open `http://127.0.0.1:8000/admin/`.
2. Log in with the superuser created above.
3. Open **Categories** and add a category.

Deleting a category sets the category of related todos to `null`; it does not
delete those todos.

## Error format

Errors use a consistent JSON shape:

```json
{
  "error": "Readable error message",
  "code": 400
}
```

Validation errors also include all field errors:

```json
{
  "error": "title: This field may not be blank. (and 1 more)",
  "code": 400,
  "details": {
    "title": ["This field may not be blank."],
    "priority": ["Must be one of: 1 (Low), 2 (Medium), 3 (High)."]
  }
}
```

An authenticated user's todo that belongs to another user returns `404`, not
`403`, to avoid revealing whether that todo exists.

## Running tests

Run all unit and integration tests:

```bash
pytest tests/unit tests/integration
```

Run only unit tests:

```bash
pytest tests/unit
```

Run only integration tests:

```bash
pytest tests/integration
```

The pytest configuration shows every test name and result. Failures include
the assertion message and full traceback.

Coverage report:

```bash
coverage erase
coverage run -m pytest tests/unit tests/integration
coverage report -m
coverage html
```

Open the HTML report at `htmlcov/index.html`.

## Important project decisions

- **PATCH instead of PUT:** updates are partial and accidental full replacement
  is prevented.
- **Hard delete:** deleting a todo permanently removes it.
- **Limit/offset pagination:** follows DRF's standard response shape and keeps
  large list responses bounded.
- **Stable ordering:** `-created_at, -id` prevents duplicate or missing rows
  across pages when timestamps are equal.
- **404 for another user's todo:** prevents an ID-existence side channel.
- **Category `SET_NULL`:** deleting a global category preserves user data.
- **Strict input fields:** booleans, integers, dates, and strings reject
  ambiguous JSON types instead of silently coercing them.
- **Redis is optional locally:** development works without Redis, while
  production should use shared Redis for consistent cache and throttling.

## Known limitations

- SQLite is suitable for this assignment and small deployments; PostgreSQL is
  preferable for larger concurrent workloads.
- `icontains` search on SQLite is not designed for large-scale full-text search.
- Bengali and other locale-specific ordering uses SQLite/code-point ordering,
  not linguistic collation.
- Without Redis, throttle counters and cache entries are process-local.
- The current repository does not yet include Docker/Compose deployment files;
  local setup uses the Python virtual environment and optional Redis.

## Security notes

- Never commit `.env`, passwords, JWT signing keys, or production database
  files.
- Use `DEBUG=false` and explicit `ALLOWED_HOSTS` in production.
- Use HTTPS for deployed API and admin traffic.
- Use a separate, strong `JWT_SIGNING_KEY` in production and rotate it if
  exposed.
