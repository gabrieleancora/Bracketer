# WSGI and deployment implementation plan

**Date:** 2026-09-24  
**Status:** Implementation handoff; deployment has not been implemented or tested.  
**Inspected baseline:** commit `3a6f404`, Python 3.12.10 in the local virtual environment.

## Outcome and proposed scope

Run Bracketer under a production WSGI server, preserve live bracket updates and votes, and keep its SQLite database across restarts and upgrades. Deliver a documented bare-host deployment first; optionally package the same application and configuration in a Linux container.

**Confirmed capacity requirement:** support up to **200 people voting concurrently**, with their live-update connections open, throughout an event. Crashes, worker restarts caused by load, lost accepted ballots, and an unresponsive owner interface are release blockers. Validate additional headroom at 300 concurrent attendee sessions plus projector/admin traffic. Configuration alone is not evidence that this requirement is met.

Proposed default: one Linux host, one application instance, Gunicorn with threaded workers, and an HTTPS reverse proxy. Keep SQLite on local persistent storage. Use Docker Compose if container packaging is selected. Kubernetes, multiple application replicas, PostgreSQL, and an ASGI rewrite are outside this initial deployment.

Gunicorn supports Linux/WSL rather than native Windows. If the deployment must run directly on Windows, use Waitress and a Windows service supervisor instead; Docker on Windows should run Linux containers. Both servers can import the existing `app:app` object. A new `wsgi.py` or application factory is not required just to serve this application. See the official [Gunicorn integration](https://flask.palletsprojects.com/en/stable/deploying/gunicorn/) and [Waitress integration](https://flask.palletsprojects.com/en/stable/deploying/waitress/) documentation.

## Findings that drive the work

| Existing behavior | Deployment implication |
| --- | --- |
| `app.py` exports `app = Flask(__name__)`; its main block calls `app.run()` | Keep the development command, but production must import `app:app` through WSGI. |
| `requirements.txt` contains Flask and qrcode only | Add and lock the production server and dependencies for the selected platform. |
| `BRACKETER_DB` selects the SQLite path; default is `instance/bracketer.sqlite3` | Set an absolute production path and persist the containing directory. |
| `init_db()` runs at module import | Make schema initialization an explicit deployment step before starting the server. |
| `SONG_INDEX` loads `data/song-info.json` at import | Include the catalog, templates, and static files in every release/image. |
| `/api/brackets/<id>/events` loops indefinitely, queries SQLite and emits an SSE event or heartbeat every second | Each open stream occupies a WSGI thread; proxy buffering and stream capacity must be tested. |
| Both `static/display.js` and `static/vote.js` open an `EventSource` | Size streams for all attendee browser tabs plus projector tabs, not just the projector. |
| Owner actions read JSON, modify it, and write it back without a transaction covering the initial read | Concurrent actions can overwrite changes; adding WSGI threads does not fix this. |
| Voting checks state before inserting a ballot | A vote can race with closing/revealing a matchup; these operations need coordinated transactions. |
| QR generation uses `request.host_url`; the voter cookie uses `secure=request.is_secure` | Preserve the external host and HTTPS scheme across the reverse proxy. |
| Owner URLs contain bearer tokens in `/owner/...` and `/api/owner/...` | Raw request paths in proxy/server logs can expose bracket control credentials. |
| Responses already set `no-store`, `no-referrer`, and `nosniff` | Preserve these headers; do not cache API, owner, or event responses. |

## Implementation order

### 1. Establish the deployment contract

Record the target OS/host, CPU/RAM limits, domain or LAN address, event duration, expected extra browser tabs, and who operates backups before deployment. The user has confirmed up to 200 voters; this is a firm minimum requirement, superseding the earlier provisional 100-stream target. Keep the Linux default and validate 300 concurrent attendee sessions for 50% headroom, in addition to projector and admin requests. Each simulated attendee must keep a separate cookie jar, consume live events, fetch updated state, and submit ballots as the real frontend does. Count extra tabs as extra streams even when they belong to the same voter.

Use Python 3.12 initially to match the inspected runtime, selecting a maintained patch release at implementation time. Resolve and pin tested dependency versions rather than using unbounded production installs. Keep Gunicorn out of native Windows installation paths, for example with separate Linux and Windows production requirements/lock files.

Define and document this configuration contract; names marked proposed do not exist yet:

| Setting | Intended behavior |
| --- | --- |
| `BRACKETER_DB` (existing) | Required absolute database path in production; container default `/var/lib/bracketer/bracketer.sqlite3`. |
| `BRACKETER_HOST`, `PORT` (existing) | Currently affect only `python app.py`; do not imply Gunicorn reads them. Document production bind settings separately. |
| `BRACKETER_BIND` (proposed) | Gunicorn configuration reads this; bare-host default `127.0.0.1:8000`, container value `0.0.0.0:8000`. |
| `BRACKETER_THREADS` (proposed) | Validated positive integer; initial load-test candidate 384 if retaining one blocking thread per SSE stream. Confirm memory and latency on the target host before adopting it. |
| `BRACKETER_BEHIND_PROXY` (proposed) | Default false; enable only for the documented single trusted proxy topology. |
| `BRACKETER_TRUSTED_HOSTS` (proposed) | Parse into Flask's trusted host configuration; list the deployment hostname and only the internal health-check hostnames actually needed. |

Do not add a Flask session secret without a consumer: the current app uses generated owner tokens and voter cookies, not Flask signed sessions.

### 2. Separate initialization from serving

1. Replace unconditional import-time `init_db()` with an explicit Flask CLI command, such as `flask --app app init-db`.
2. Keep initialization idempotent for the existing schema. Adjust the development main block and test setup to initialize explicitly so their existing workflows still work.
3. Production startup runs initialization once, as the application user, before accepting traffic. Existing data must never be cleared. Perform future schema migrations as controlled release steps, not on each worker import.
4. Fail startup with a useful error if the configured directory is not writable, the schema is unavailable, or the song catalog is missing/invalid. Verify an actual database operation during startup.
5. Add `/healthz` for a cheap process response and `/readyz` for a bounded query of required database tables. Return 503 when readiness fails without exposing paths, credentials, or stack traces. A health request must not silently create a replacement empty database.

### 3. Make shared database changes safe under concurrency

This is a correctness prerequisite for the threaded deployment. One worker process still handles simultaneous requests.

- For owner mutations and vote submission, acquire a short SQLite write transaction **before reading the bracket or checking its voting state**. `BEGIN IMMEDIATE` is a suitable starting approach. Re-read and validate state within the transaction, perform all related changes, then commit once.
- Include settings, manual winners, video edits, vote controls, and ballot insertion. In particular, closing/revealing and ballot acceptance must serialize: a ballot accepted before close commits is counted; one checking state after close commits is rejected.
- Refactor `save_bracket()` so an inner commit cannot split the encompassing transaction. Roll back every failed operation, including early validation returns. Do not automatically replay a stale JSON mutation after a lock failure.
- Preserve the unique ballot constraint and its 409 response. Map exhausted database lock waits to a controlled retryable response such as 503, with safe logging, rather than an unhandled traceback.
- Keep per-request connections. Use consistent foreign-key and busy-timeout settings on relevant connections, and close the SSE polling connection even if a query raises. Never keep a write transaction open across a stream yield or sleep.
- Consider WAL at initialization to reduce contention between reads and writes, then test it on the target local filesystem. WAL does not fix stale read/modify/write logic. Persist the entire database directory, including SQLite sidecar files, and avoid a network filesystem for this deployment.
- Test synchronized 200-voter and 300-voter bursts explicitly. WAL still permits only one writer at a time, so keep write transactions short, measure lock-wait latency and checkpoint behavior, and do not treat a larger timeout as a throughput fix. See SQLite's [WAL concurrency documentation](https://www.sqlite.org/wal.html). A controlled 503 protects the process during excess load, but any such response during the required capacity tests is a failure to meet the capacity target.

The transaction choice follows SQLite's documented [isolation and `BEGIN IMMEDIATE` behavior](https://www.sqlite.org/isolation.html). Add deterministic concurrency tests around the actual races rather than relying on a sequential happy-path suite.

### 4. Configure the WSGI server and process lifecycle

Create `gunicorn.conf.py`, with the initial settings below. These are proposed values to validate under load, not measurements:

| Setting | Initial value / requirement |
| --- | --- |
| Application | `app:app` |
| Workers | 1 |
| Worker class | `gthread` |
| Threads | 384, configurable; an unverified starting candidate for the current blocking SSE implementation |
| Bind | Read `BRACKETER_BIND` as described above |
| Worker timeout | 60 seconds; verify that healthy SSE connections outlive this value |
| Graceful timeout | 30 seconds; supervisor/container stop allowance at least 45 seconds |
| Development features | Debug and reload disabled |
| Logs | Errors to stderr; sanitized request metadata to stdout |

Use `gunicorn --config gunicorn.conf.py app:app` from the repository/release root after initialization. Gunicorn exposes worker, thread, timeout, and logging settings through its [configuration reference](https://gunicorn.org/reference/settings/).

The capacity reasoning is specific to this application: 300 attendee streams plus two projector streams can occupy 302 of 384 threads, leaving a provisional 82 threads for voting, administration, state fetches, and probes. The previous 128-thread candidate cannot accommodate even 200 persistent attendee streams. Each stream also performs approximately one database poll per second, so test roughly 302 polls/second plus synchronized state fetches and ballot writes. Available threads do not guarantee database throughput or acceptable memory use; measure both.

Budget WSGI connection limits, proxy connections, file descriptors, thread memory, and container CPU/RAM for the combined workload. Proxying requires both client-side and upstream connections. Keep measured resource headroom under the actual production limits and test slow/disconnected clients releasing their resources. Bound pending work and excess stream admissions so overload cannot consume every resource needed for voting, admin controls, and probes. Avoid strict per-IP limits that would block 200 attendees sharing an event Wi-Fi gateway.

If this threaded candidate cannot pass the capacity tests, revise the implementation before deployment. Options include a separately tested cooperative streaming server or moving attendee updates to short, staggered polling while retaining projector SSE and the required update latency. Switching to gevent requires validating blocking SQLite work and monkey-patching behavior. If serialized database writes remain the measured bottleneck after transaction fixes, revise the database design. Increasing thread counts indefinitely, adding a container, or restarting failed workers does not establish reliability. Document any necessary architecture change and rerun the full acceptance workload.

Provide a Linux systemd service example using an unprivileged account, absolute paths, an environment file, an initialization pre-start command, restart-on-failure, and the shutdown allowance above. Do not daemonize Gunicorn inside systemd or a container.

If native Windows is selected instead, provide a tested equivalent beginning with `waitress-serve --host=127.0.0.1 --port=8000 --threads=384 app:app`, explicit database initialization, and a documented service startup/restart mechanism. This thread count is also an unverified candidate; run the same SSE, resource-budget, and capacity checks on Windows.

### 5. Add the reverse proxy and HTTPS configuration

Use one trusted Nginx proxy for the reference Linux deployment. A managed ingress can replace it if it passes the same checks.

- Publish only the proxy. Bind the bare-host WSGI listener to loopback; for a container, keep port 8000 on the private Compose network without a public host port.
- Terminate HTTPS at the proxy for public deployment; document certificate provisioning, renewal, and HTTP-to-HTTPS redirects. A LAN-only HTTP example must use the reachable LAN address in its URLs and must leave proxy trust disabled if connecting directly.
- Preserve the allowed external `Host`; overwrite forwarded scheme and client-address headers at the trusted edge rather than accepting client values. Reject unknown hosts. Coordinate any WSGI-server forwarded-header handling with the Flask middleware.
- When the single-proxy flag is enabled, configure `ProxyFix` only for headers actually supplied: for example `x_for=1`, `x_proto=1`, with `x_host=0`, `x_port=0`, and `x_prefix=0` when the original allowed Host is forwarded directly and the app is served at `/`. Do not enable trust for all header types by default. See Flask's [proxy trust guidance](https://flask.palletsprojects.com/en/stable/deploying/proxy_fix/).
- For `/api/brackets/<id>/events`, explicitly disable response buffering, caching, and compression; preserve the existing `X-Accel-Buffering: no`. Use upstream HTTP/1.1, clear an inappropriate upstream `Connection` header, and set a read timeout comfortably above the one-second heartbeat, initially 75 seconds. This is SSE, so WebSocket upgrade configuration is unnecessary. Nginx documents [buffering and proxy timeouts](https://nginx.org/en/docs/http/ngx_http_proxy_module.html).
- Check any external load balancer/CDN stream-duration and idle limits too. A local Nginx configuration cannot override an upstream platform limit.
- Set an explicit request-body limit in both Flask and the proxy, initially 64 KiB, and verify valid 64-entry brackets with long Unicode names still fit.
- Preserve existing response privacy headers. Serve static assets through the app initially; defer cache policy changes to a separate optimization.
- Avoid raw URLs, queries, request bodies, cookies, and owner-token headers in logs. Use route templates in application request logs and omit or redact URI fields in proxy/Gunicorn logs. Test both successful requests and error logs with a recognizable test token. Log method, sanitized route, status, duration, and a request identifier where available.

### 6. Optional container packaging

Add this phase if Linux containers are selected; it is not required to obtain a production WSGI server.

1. Add a `Dockerfile` using a maintained Python 3.12 slim image; record/pin the tested image digest and provide an update process. Install the locked Linux requirements before copying application files for build caching.
2. Explicitly copy `app.py`, server configuration, `templates/`, `static/`, and `data/song-info.json`, plus startup/operations scripts. Avoid copying a developer database into the image.
3. Create a fixed unprivileged UID/GID and a writable `/var/lib/bracketer` directory. Run initialization and Gunicorn as that user. Document volume ownership setup for both an empty named volume and an existing bind mount; fail clearly on permission problems rather than using world-writable permissions.
4. Add an entrypoint that performs initialization, validates readiness prerequisites, then uses `exec` to replace itself with Gunicorn. Keep the executable startup script in LF format for Linux. The image build must not create or migrate a production database.
5. Add `.dockerignore` excluding `.git`, `.venv`, caches, `instance`, database files/sidecars, backups, `.env`, and unrelated planning/reference assets. Use Docker's [build guidance](https://docs.docker.com/build/building/best-practices/) for image construction and non-root execution.
6. Add `compose.yaml` with application and proxy services, one named database volume mounted at `/var/lib/bracketer`, restart policies, a bounded `/readyz` health check, and a 45-second stop grace period. Use Python's standard library for an in-container HTTP probe if curl is absent. Persist TLS material as appropriate without embedding private keys in the image.
7. Keep release source immutable inside production containers; do not bind-mount the working tree. Configure bounded log rotation. Document that an unhealthy Docker health status alone does not trigger a restart; process crashes and readiness failures need distinct operational handling.
8. Add `.env.example` for non-secret placeholders and ignore the actual `.env` file in Git. Clarify that Compose interpolation does not automatically pass every variable to the application: declare required environment variables explicitly.

### 7. Provide the operations runbook

Create `docs/DEPLOYMENT.md` with exact commands for the chosen path: installation/build, initial storage setup, initialization, start, status, safe log inspection, restart, upgrade, rollback, backup, and restore. Add a short link from `README.md` and clearly label `python app.py` as development.

- Back up the current database before first migration/deployment and before releases. Use SQLite's backup API (Python `sqlite3.Connection.backup`) or stop all writers before copying; do not copy only a live main database file. The [SQLite backup documentation](https://www.sqlite.org/backup.html) describes consistent online snapshots.
- If moving the current development database into production, stop writes during cutover and restore a consistent backup into the provisioned production volume with the correct ownership. Do not silently start with an empty database.
- Store backups away from the application volume and restrict access: they contain owner tokens and voter identifiers. Document a proposed daily schedule plus pre/post-event backups, retention, and the operator responsible for scheduling; agree the acceptable data-loss window before launch.
- Restore to a temporary separate database first, run `PRAGMA integrity_check`, and verify bracket state and ballots. Document restoring to production during a maintenance window.
- Tag releases/images immutably. For rollback, return to the previous application release using the existing database only when schema-compatible. Otherwise use the pre-upgrade backup and explicitly account for votes submitted since that backup.
- Restarts can interrupt SSE streams. Verify browser reconnection and full-state refresh after a new stream opens; plan upgrades between voting rounds and describe the brief interruption. Do not promise zero downtime from a single instance.
- Document that `docker compose down -v` deletes the database volume and must not be part of routine upgrade commands.
- Monitor availability, errors, request latency, active streams/thread pressure, SQLite lock failures, disk space, and backup success. Keep health probes out of noisy access logs where practical.

## Files to deliver

| File | Work |
| --- | --- |
| `app.py` | Explicit initialization command, transaction boundaries, health routes, environment validation, host/proxy configuration, body limit, safe operational errors/logging. |
| Production dependency/lock files | Reproducible Linux WSGI dependencies; Windows alternative only if selected. |
| `gunicorn.conf.py` | Threaded server configuration and sanitized logs. |
| `deploy/nginx.conf.example` | HTTPS/proxy/SSE template with clearly marked deployment placeholders. |
| `deploy/bracketer.service.example` | Bare-Linux service lifecycle and storage/account setup instructions. |
| `tests/test_app.py` and deployment tests | Preserve existing flows; verify transactions, proxy behavior, startup, and health failures. |
| `scripts/smoke_deployment.py` | HTTP smoke checks against an actual server, using an isolated test database. |
| Load-test suite and results | Reproducible 200/300-attendee bursts, sustained voting, reconnection and overload scenarios; record host resources, dependency versions, configuration, metrics, and ballot reconciliation. |
| `scripts/backup_db.py` | Consistent SQLite backup with verification and meaningful exit status. |
| `docs/DEPLOYMENT.md`, `README.md` | Operator runbook and development/production distinction. |
| Optional `Dockerfile`, `.dockerignore`, `compose.yaml`, `deploy/entrypoint.sh`, `.env.example`, `.gitignore` | Container packaging and persistence. |

## Acceptance checks for the implementing agent

Run against disposable databases and separate test volumes. Existing user data must not be used for load tests.

1. Run `python -m unittest discover -s tests -v`; all existing flows pass after explicit initialization is introduced. Check installation from locked requirements and dependency consistency in a clean environment.
2. Start the actual selected WSGI server with debug/reload disabled. Test home, static assets, song lookup, creation, owner authorization, publication, manual winners, public voting, QR output, and health routes. Test startup from both empty and populated databases, including failed storage permissions/missing catalog.
3. Use independent connections and coordinated concurrency tests to prove owner writes do not silently overwrite each other and close/reveal cannot omit a ballot that was accepted before close. Verify duplicate submissions with the same existing voter cookie produce one ballot and the expected conflict response. Preserve the documented limitations of anonymous cookies.
4. Through HTTPS, decode the QR payload and confirm the external HTTPS host. Verify the voter cookie has Secure, HttpOnly, and SameSite=Lax. Verify untrusted hosts fail and supplied forwarded headers cannot spoof the public scheme/host through the edge.
5. Pass all scenarios in the capacity gate below through the actual proxy and WSGI server with production CPU/RAM limits. Flask's in-process test client and idle SSE connections alone are insufficient. Record results; adjust configuration or architecture if any requirement fails.
6. Observe incremental SSE output with an unbuffered HTTP client; verify one-second heartbeats, updates, unpublish termination, disconnect cleanup, and reconnect after restart. Keep streams open beyond configured worker/proxy timeouts to catch premature disconnections.
7. Submit a recognizable test owner token and inspect proxy, application, server, and error logs. The token, cookie value, and request bodies must not appear.
8. Restart the process and, if containerized, recreate the application container. Saved brackets, ownership, and ballots survive. Verify non-root operation and that only intended storage paths need writes. Verify the WSGI port is unreachable externally when the proxy is in use.
9. Produce a backup, restore it into separate storage, validate integrity and the full voting state, and rehearse release rollback. Document any downtime and possible data loss in a restore-based rollback.
10. If containers are implemented, validate `docker compose config`, build cleanly, verify readiness and stop timing, and run the same smoke checks against the Compose deployment. Report checks that require an unavailable Linux/Docker host as unverified, not passed.

## Capacity gate: 200 voters and event-length reliability

Use an isolated deployment on the intended host or equivalent hardware, with the load generator running separately so its resource use does not distort results. Exercise the real request sequence, including initial page/static loads, independent voter cookies, SSE consumption, state fetches after version changes, and vote submissions. Use multiple brackets as needed to continue voting throughout the test; repeat requests to an already-voted matchup are not a valid voting-throughput test.

| Scenario | Required workload and evidence |
| --- | --- |
| Arrival and synchronized voting | Connect 200 attendees plus two projector displays, load their pages, open voting, then release all 200 ballot requests within one second. Repeat across at least 20 matchups while exercising close/reveal/advance. Repeat the scenario with 300 attendees for headroom. |
| Sustained event | Hold 200 attendee sessions plus displays for at least two hours, or the planned event length if longer. Submit a 200-ballot burst at least once per minute across fresh matchups, operate owner controls, and periodically replace disconnected clients. Also run the 300-attendee workload for at least 30 minutes. |
| Correctness during contention | For ordinary open-round bursts, verify exactly one stored ballot per intended voter, the expected total and choices, and the revealed winner. Separately race vote submissions with close/reveal: record expected state rejections, and reconcile every successful response with durable storage and the revealed totals. |
| Reconnect surge | Disconnect and reconnect all 200 attendees during an open round. Verify current state is restored within ten seconds after connectivity returns, old streams release resources, existing cookies survive, and a previously accepted vote is not duplicated. Test first-time voters as well as voters with established cookies. |
| Excess load and recovery | Increase traffic beyond the measured capacity in a separate controlled test. Excess work may receive bounded, explicit rejection, but must not crash or exhaust the process. After returning to the supported load, restore normal latency within 30 seconds without an operator restart. Recheck stored ballot integrity. |

For the 200-voter baseline and 300-voter headroom scenarios, require **zero load-induced crashes, OOM kills, worker restarts, unexpected disconnects, request timeouts, or 5xx responses**. Deliberate invalid/duplicate/closed-round requests are counted separately and must receive their expected responses. Keep voting and owner/API request latency below **two seconds at p95 and five seconds at p99**; deliver state changes to connected clients within **three seconds**. Measure latency from the intended request launch time so client-side queueing cannot hide overload.

During the sustained test, record process/container memory, CPU, active threads/streams, open descriptors/database connections, disk/WAL growth, lock waits, response latency, and worker exits. After warm-up, resource use must stabilize with no continuing leak across repeated disconnect/reconnect cycles. Verify at least 25% memory headroom against the configured limit during the measured peak. Record CPU and storage specifications and any throttling; do not infer a supported host size from thread count alone.

Any crash, unexplained lost or duplicated accepted ballot, stalled administration, or failure of these latency/resource checks blocks production readiness. Automatic restart policies are recovery mechanisms and cannot turn a failed sustained-load test into a pass. No load tests have been run as part of this planning task.

## Completion report expected from the next agent

List the files changed, supported launch commands, selected platform/runtime, measured stream capacity, 200/300-voter burst and sustained-test results, target host CPU/RAM and configured limits, storage/backup locations, and remaining host-specific values (domain, certificate provisioning, volume ownership, or service account). Link the operator runbook and load-test report. Do not describe the application as deployed or ready for 200 voters until it has actually passed the capacity gate on the target host or equivalent hardware.
