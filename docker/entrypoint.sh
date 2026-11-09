#!/bin/sh
set -eu

python manage.py migrate --noinput
if [ "${COLLECTSTATIC:-true}" = "true" ]; then
    python manage.py collectstatic --noinput
fi

exec "$@"
