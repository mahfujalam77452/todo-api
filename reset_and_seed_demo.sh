#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${SCRIPT_DIR}/venv/bin/python"
PASSWORD='@#abcd@#1234@#'

if [[ ! -x "${PYTHON}" ]]; then
  echo "Virtualenv interpreter not found: ${PYTHON}" >&2
  exit 1
fi

cd "${SCRIPT_DIR}"

# This script is for local demo reset/seeding. Do not require a running Redis
# instance or produce Redis connection noise; Django falls back to local memory.
export REDIS_URL=

echo "Applying database migrations..."
"${PYTHON}" manage.py migrate --noinput

echo "Deleting existing database data..."
"${PYTHON}" manage.py flush --noinput

echo "Creating demo admin, users, teams, Scrums, and dashboard activity..."
"${PYTHON}" manage.py seed_demo_dashboard --password "${PASSWORD}"

echo "Adding Project Managers, team activity, notifications and bulk emails..."
"${PYTHON}" manage.py seed_demo_data --password "${PASSWORD}"

echo
echo "Demo workspace is ready."
echo "Admin email: demo-admin@example.com"
echo "Project Managers: engineering-one@example.com (Engineering), design-one@example.com (Design)"
echo "Admin/user password: ${PASSWORD}"
echo
echo "Next steps (details in README.md):"
echo "  1) Redis:   docker run -d --name todo-redis -p 6379:6379 redis:7-alpine   (or: docker start todo-redis)"
echo "  2) API:     python manage.py runserver"
echo "  3) Worker:  celery -A config worker -l info      (emails are printed in this terminal)"
echo "  4) Beat:    celery -A config beat -l info        (nightly PDF at 00:00 Asia/Dhaka)"
echo "  No Redis?   set CELERY_TASK_ALWAYS_EAGER=true and REDIS_URL= in .env (emails print in the runserver terminal)"
echo "  PDF now:    python manage.py send_daily_summary --force   (saved in reports/)"