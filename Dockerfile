FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BRACKETER_DB=/var/lib/bracketer/bracketer.sqlite3 \
    BRACKETER_BIND=0.0.0.0:8000 \
    BRACKETER_TRUST_PROXY=1

WORKDIR /app
COPY requirements.txt requirements-linux.txt ./
RUN python -m pip install --no-cache-dir -r requirements-linux.txt \
    && groupadd --gid 10001 bracketer \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin bracketer \
    && mkdir -p /var/lib/bracketer \
    && chown 10001:10001 /var/lib/bracketer

COPY app.py gunicorn.conf.py ./
COPY templates/ ./templates/
COPY static/ ./static/
COPY data/song-info.json ./data/song-info.json
COPY deploy/entrypoint.sh /entrypoint.sh
RUN chmod 0555 /entrypoint.sh

USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
