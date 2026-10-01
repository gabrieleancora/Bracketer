"""Linux WSGI settings for the single-instance deployment."""

import os


def positive_int(name, default):
    value = int(os.environ.get(name, default))
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


bind = os.environ.get("BRACKETER_BIND", "127.0.0.1:8000")
workers = 1
worker_class = "gthread"
# A starting value only. Each live SSE connection occupies a thread.
threads = positive_int("BRACKETER_THREADS", "384")
timeout = 60
graceful_timeout = 30
keepalive = 5
reload = False
daemon = False
errorlog = "-"
accesslog = None  # Owner tokens are embedded in URL paths.
capture_output = False

# Safe only when port 8000 is reachable solely from the trusted reverse proxy.
forwarded_allow_ips = "*" if os.environ.get("BRACKETER_TRUST_PROXY") == "1" else "127.0.0.1"
secure_scheme_headers = {"X-FORWARDED-PROTO": "https"}
