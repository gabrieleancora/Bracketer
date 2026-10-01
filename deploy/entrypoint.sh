#!/bin/sh
set -eu

case "${BRACKETER_DB:-}" in
    /*) ;;
    *) echo "BRACKETER_DB must be an absolute path" >&2; exit 1 ;;
esac

db_dir=$(dirname "$BRACKETER_DB")
if [ ! -d "$db_dir" ] || [ ! -w "$db_dir" ]; then
    echo "Database directory is missing or not writable by UID 10001: $db_dir" >&2
    exit 1
fi

python -m flask --app app init-db
python -c 'from app import app; c=app.test_client(); assert c.get("/readyz", base_url="http://127.0.0.1").status_code == 200, "Database is not ready"'
exec gunicorn --config gunicorn.conf.py app:app
