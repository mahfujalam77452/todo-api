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
echo "Run the API with REDIS_URL empty to see emails in the console:"
echo "  REDIS_URL= python manage.py runserver"
echo "Send the daily PDF summary now (no need to wait for midnight):"
echo "  python manage.py send_daily_summary --force"