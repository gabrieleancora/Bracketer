# Bracketer deployment handoff

This repository has a Linux container path: one Gunicorn process, one Caddy HTTPS proxy, and a persistent SQLite volume. The application serializes owner edits and ballots, initializes the schema explicitly, and provides `/healthz` and `/readyz`. This is **not a production readiness claim**. The 200/300-attendee capacity gate in [the deployment plan](../planning/DEPLOYMENT_PLAN.md) still needs to pass on the target host. Do not run a 200-voter event until it does.

## Host and DNS

Use a Linux host with Docker Engine and the Compose plugin. Reserve its public IP. Create an `A` record for the chosen name, such as `brackets.example.com`, pointing to that IPv4 address. Add an `AAAA` record only if the host really accepts IPv6 traffic. Allow inbound TCP 80 and 443 and, optionally, UDP 443 for HTTP/3; allow the host outbound access for certificate issuance. If the host is behind a router, forward TCP 80/443 to it. Do not forward port 8000. Caddy obtains and renews the public TLS certificate after DNS and reachability work. Use the public HTTPS hostname for the owner page before generating QR codes.

Do not put a CDN or another reverse proxy in front without revisiting forwarding trust and stream limits. The current layout has one trusted edge proxy. The `BRACKETER_TRUST_PROXY=1` setting makes Gunicorn accept forwarded scheme headers from any IP, so the application port must remain private on the Compose network. The Compose file publishes only Caddy's ports.

## Build and start

Run from the repository root on the Linux host:

```sh
cp .env.example .env
# Edit .env: set BRACKETER_DOMAIN to the real DNS name.
docker compose config
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail=100 app proxy
```

The database lives in the `bracketer-data` named volume at `/var/lib/bracketer/bracketer.sqlite3`; Caddy's certificate data lives in `caddy-data`. The image runs as UID/GID 10001. Docker initializes a new named volume from the owned image directory. For an existing bind mount substituted for that volume, provision its directory for UID/GID 10001 before starting. The entrypoint checks access, runs the idempotent `flask --app app init-db` command, verifies readiness, and starts Gunicorn. SQLite uses WAL mode, so persist the entire database directory including its sidecar files.

The app has no public port mapping. Caddy routes only the configured hostname and handles HTTPS. It caps request bodies at 64 KiB and flushes streaming responses immediately. Flask also limits bodies to 64 KiB and accepts only the configured domain and local health-check host. Gunicorn has one `gthread` worker and a candidate of 384 threads; this number has **not** been validated for memory, SQLite contention, or voter capacity. App access logging is disabled because owner tokens appear in URL paths. Keep Docker logs private; inspect them with `docker compose logs --tail=100 app proxy`. An unhealthy container does not automatically restart just because its health check fails.

For a bare Linux host, use [the systemd unit](../deploy/bracketer.service.example) and [the Nginx proxy example](../deploy/nginx.conf.example). Install `requirements-linux.txt` in a Python 3.12 virtual environment under `/opt/bracketer/current`, create the `bracketer` service account and an owned `/var/lib/bracketer` directory, and create `/etc/bracketer/bracketer.env` with `BRACKETER_DB=/var/lib/bracketer/bracketer.sqlite3`, `BRACKETER_BIND=127.0.0.1:8000`, `BRACKETER_TRUST_PROXY=1`, and `BRACKETER_TRUSTED_HOSTS=brackets.example.com,127.0.0.1` (replace the example name). Restrict that environment file to the operator and service account. Set the real hostname and certificate paths in the Nginx file; obtain the certificate through the host's ACME/Certbot process and test renewal. Copy the unit to `/etc/systemd/system/bracketer.service`, then run `systemctl daemon-reload`, `systemctl enable --now bracketer`, and `systemctl status bracketer`. Validate the Nginx configuration with `nginx -t` before reload. Keep the Gunicorn listener on loopback. `python app.py` is the development server.

## Operations

Check the public home page and a real bracket through `https://<domain>/`. Check that the QR URL uses HTTPS and the correct hostname, that voting cookies have `Secure`, and that an SSE client receives heartbeats and updates. The current Compose health check confirms an HTTP response and table queries; it is not a substitute for application readiness or a ballot test.

Restart or upgrade between voting rounds, since one instance interrupts live streams:

```sh
docker compose restart app
# For a source/image upgrade after taking a backup:
docker compose build app
docker compose up -d --no-deps app
docker compose ps
```

Keep an immutable release tag or image digest for rollback. Reuse the existing database only for schema-compatible rollback; if schema changed, restore the pre-upgrade backup and account for votes since it. Never use `docker compose down -v` during normal operations: it deletes the database and certificate volumes.

### Consistent backup

The database includes owner credentials and voter IDs. Restrict backup access and store copies away from this host. The following uses SQLite's online backup API, then copies the completed snapshot outside the application volume. Use a unique timestamp in place of `YYYYMMDD-HHMM` and ensure `backups/` is private:

```sh
mkdir -m 700 -p backups
docker compose exec -T app python -c "import sqlite3; s=sqlite3.connect('/var/lib/bracketer/bracketer.sqlite3'); d=sqlite3.connect('/var/lib/bracketer/export.sqlite3'); s.backup(d); d.close(); s.close()"
docker compose cp app:/var/lib/bracketer/export.sqlite3 backups/bracketer-YYYYMMDD-HHMM.sqlite3
docker compose exec -T app rm /var/lib/bracketer/export.sqlite3
chmod 600 backups/bracketer-YYYYMMDD-HHMM.sqlite3
```

Schedule daily and pre/post-event backups with an operator-owned scheduler after agreeing the acceptable data-loss window and retention. Test restores regularly. Avoid copying just a live `.sqlite3` file because live SQLite may have WAL sidecars.

### Restore rehearsal and production restore

First verify a backup in a separate temporary directory, without starting the app against it:

```sh
python3 -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute('PRAGMA integrity_check').fetchone()[0]); print('brackets',c.execute('SELECT count(*) FROM brackets').fetchone()[0]); print('votes',c.execute('SELECT count(*) FROM votes').fetchone()[0])" backups/bracketer-YYYYMMDD-HHMM.sqlite3
```

Review representative bracket state and ballot counts. For a production restore, announce a maintenance window, take a fresh backup, then stop both services. Replace the volume database from the verified backup using an operator-controlled helper container or equivalent volume tool, remove stale WAL/SHM sidecars while all writers are stopped, set ownership to UID/GID 10001, and start the services. Verify the state again through HTTPS. Do not restore an older snapshot while accepting votes; votes after its timestamp would be lost.

## Remaining release gates

Local functional checks on 2026-09-24 used `python -m unittest discover -s tests -v` (8 passing tests) and `python scripts/local_burst.py 200` / `python scripts/local_burst.py 300` against isolated SQLite databases through Flask's in-process test client on Windows. The 200-voter burst stored 200/200 ballots (p95 3.001s, p99 3.248s); the 300-voter burst stored 300/300 (p95 4.797s, p99 5.200s). These measurements exceed the plan's latency targets and omit SSE streams, the WSGI server, HTTPS proxy, and sustained traffic. They are correctness checks only; do not use them as proof of event capacity.

Pin the resolved Python dependency tree and base/proxy image digests for an actual release. Validate `docker compose config`, image builds, startup, stop behavior, logs, backups, SSE behavior, and the 200/300-attendee capacity scenarios on Linux. Docker was unavailable in the implementation workspace, so these checks have not yet run.
