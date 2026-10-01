import io
import json
import os
import random
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

import click
import qrcode
import qrcode.image.svg
from flask import Flask, Response, abort, g, jsonify, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix


ROOT = Path(__file__).parent
DB_PATH = Path(os.environ.get("BRACKETER_DB", ROOT / "instance" / "bracketer.sqlite3")).expanduser().resolve()
SONGS_PATH = ROOT / "data" / "song-info.json"
app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
trusted_hosts = os.environ.get("BRACKETER_TRUSTED_HOSTS")
if trusted_hosts:
    app.config["TRUSTED_HOSTS"] = [host.strip() for host in trusted_hosts.split(",") if host.strip()]
if os.environ.get("BRACKETER_TRUST_PROXY") == "1":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)


def song_index():
    songs = json.loads(SONGS_PATH.read_text(encoding="utf-8"))
    index = {}
    for song in songs:
        video_id = (song.get("musicVideo") or {}).get("videoId")
        if not video_id:
            continue
        for field in ("name", "englishName"):
            name = song.get(field)
            if name:
                index.setdefault(name.strip().casefold(), set()).add(video_id)
    return index


SONG_INDEX = song_index()
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def db():
    if "db" not in g:
        g.db = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=rw", uri=True, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@contextmanager
def write_transaction():
    connection = db()
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
    finally:
        if connection.in_transaction:
            connection.rollback()


@app.teardown_appcontext
def close_db(error):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    try:
        mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        if mode.lower() != "wal":
            raise RuntimeError("SQLite WAL mode is unavailable for the configured database.")
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS brackets (
                id TEXT PRIMARY KEY,
                owner_token TEXT NOT NULL,
                title TEXT NOT NULL,
                data TEXT NOT NULL,
                published INTEGER NOT NULL DEFAULT 0,
                public_voting INTEGER NOT NULL DEFAULT 0,
                version INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS votes (
                bracket_id TEXT NOT NULL,
                match_id TEXT NOT NULL,
                voter TEXT NOT NULL,
                choice INTEGER NOT NULL,
                PRIMARY KEY (bracket_id, match_id, voter),
                FOREIGN KEY (bracket_id) REFERENCES brackets(id)
            );
        """)
    finally:
        connection.close()


@app.cli.command("init-db")
def init_db_command():
    init_db()
    click.echo("Database initialized.")


def fail(message, status=400):
    return jsonify(error=message), status


def get_bracket(bracket_id, owner=False):
    row = db().execute("SELECT * FROM brackets WHERE id=?", (bracket_id,)).fetchone()
    if row is None:
        abort(404)
    if owner:
        supplied = request.view_args.get("token") or request.headers.get("X-Owner-Token", "")
        if not secrets.compare_digest(str(supplied), row["owner_token"]):
            abort(404)
    elif not row["published"]:
        abort(404)
    return row, json.loads(row["data"])


def save_bracket(row, data, **fields):
    values = {"data": json.dumps(data, ensure_ascii=False), "version": row["version"] + 1, **fields}
    assignments = ", ".join(f"{name}=?" for name in values)
    db().execute(f"UPDATE brackets SET {assignments} WHERE id=?", (*values.values(), row["id"]))


@app.errorhandler(sqlite3.OperationalError)
def database_operational_error(error):
    if "locked" in str(error).lower() or "busy" in str(error).lower():
        return fail("Database is busy. Please retry.", 503)
    app.logger.exception("Database operation failed")
    return fail("Database unavailable.", 503)


def find_match(data, match_id):
    for round_matches in data["rounds"]:
        for match in round_matches:
            if match["id"] == match_id:
                return match
    return None


def next_match(data):
    for round_matches in data["rounds"]:
        for match in round_matches:
            if match["a"] is not None and match["b"] is not None and match["winner"] is None:
                return match
    return None


def propagate(data):
    for round_number in range(1, len(data["rounds"])):
        previous = data["rounds"][round_number - 1]
        for index, match in enumerate(data["rounds"][round_number]):
            a = previous[2 * index]["winner"]
            b = previous[2 * index + 1]["winner"]
            if match["a"] != a or match["b"] != b:
                match.update(a=a, b=b, winner=None)


def vote_counts(bracket_id, match_id):
    return {row["choice"]: row["count"] for row in db().execute(
        "SELECT choice, COUNT(*) AS count FROM votes WHERE bracket_id=? AND match_id=? GROUP BY choice",
        (bracket_id, match_id),
    )}


def public_state(row, data, owner=False):
    state = {
        "id": row["id"], "title": row["title"], "entries": data["entries"],
        "rounds": data["rounds"], "voting": data["voting"],
        "published": bool(row["published"]), "public_voting": bool(row["public_voting"]),
        "love_live": data["love_live"],
        "version": row["version"],
    }
    if row["public_voting"]:
        revealed = {match["id"]: match for round_matches in data["rounds"]
                    for match in round_matches if match["winner"] is not None}
        counts = {match_id: {str(match["a"]): 0, str(match["b"]): 0}
                  for match_id, match in revealed.items()}
        if revealed:
            for vote in db().execute(
                "SELECT match_id, choice, COUNT(*) AS count FROM votes WHERE bracket_id=? GROUP BY match_id, choice",
                (row["id"],),
            ):
                if vote["match_id"] in counts:
                    counts[vote["match_id"]][str(vote["choice"])] = vote["count"]
        state["results"] = counts
    if owner:
        current = data["voting"]["current"]
        if current and data["voting"]["phase"] in ("closed", "revealed"):
            state["counts"] = vote_counts(row["id"], current)
    else:
        voter = request.cookies.get("bracketer_voter")
        current = data["voting"]["current"]
        ballot = (db().execute(
            "SELECT choice FROM votes WHERE bracket_id=? AND match_id=? AND voter=?",
            (row["id"], current, voter),
        ).fetchone() if voter and current else None)
        state["has_voted"] = ballot is not None
        state["vote_choice"] = ballot["choice"] if ballot else None
    return state


@app.after_request
def private_headers(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/healthz")
def healthz():
    return jsonify(ok=True)


@app.get("/readyz")
def readyz():
    try:
        connection = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True, timeout=1)
        try:
            connection.execute("SELECT 1 FROM brackets LIMIT 1").fetchone()
            connection.execute("SELECT 1 FROM votes LIMIT 1").fetchone()
        finally:
            connection.close()
    except sqlite3.Error:
        return fail("Database unavailable.", 503)
    return jsonify(ok=True)


@app.post("/api/brackets")
def create_bracket():
    body = request.get_json(silent=True) or {}
    title = str(body.get("title", "")).strip()
    names = body.get("names")
    if not title or len(title) > 100:
        return fail("Enter a title of at most 100 characters.")
    if not isinstance(names, list) or len(names) < 2 or len(names) & (len(names) - 1) or len(names) > 64:
        return fail("Use a power-of-two number of entries, from 2 to 64.")
    if any(not isinstance(name, str) or not name.strip() or len(name.strip()) > 100 for name in names):
        return fail("Each entry needs a name of at most 100 characters.")
    love_live = bool(body.get("love_live"))
    entries = []
    for index, name in enumerate(names):
        name = name.strip()
        matches = SONG_INDEX.get(name.casefold(), set()) if love_live else set()
        video_id = next(iter(matches)) if len(matches) == 1 else None
        entries.append({"id": index, "name": name, "video_id": video_id, "matched": bool(video_id)})
    order = list(range(len(entries)))
    random.SystemRandom().shuffle(order)
    rounds = []
    count = len(entries) // 2
    round_number = 0
    while count:
        matches = []
        for index in range(count):
            matches.append({
                "id": f"r{round_number}m{index}",
                "a": order[2 * index] if round_number == 0 else None,
                "b": order[2 * index + 1] if round_number == 0 else None,
                "winner": None,
            })
        rounds.append(matches)
        count //= 2
        round_number += 1
    bracket_id = secrets.token_urlsafe(9)
    token = secrets.token_urlsafe(32)
    data = {"entries": entries, "rounds": rounds, "voting": {"current": None, "phase": "idle"}, "love_live": love_live}
    with write_transaction() as connection:
        connection.execute("INSERT INTO brackets (id,owner_token,title,data) VALUES (?,?,?,?)",
                           (bracket_id, token, title, json.dumps(data, ensure_ascii=False)))
        connection.commit()
    return jsonify(owner_url=f"/owner/{bracket_id}/{token}"), 201


@app.get("/owner/<bracket_id>/<token>")
def owner_page(bracket_id, token):
    get_bracket(bracket_id, owner=True)
    return render_template("bracket.html", bracket_id=bracket_id, token=token, owner=True)


@app.get("/b/<bracket_id>")
def visitor_page(bracket_id):
    get_bracket(bracket_id)
    return render_template("bracket.html", bracket_id=bracket_id, token=None, owner=False)


@app.get("/vote/<bracket_id>")
def attendee_page(bracket_id):
    row, data = get_bracket(bracket_id)
    if not row["public_voting"]:
        abort(404)
    return render_template("vote.html", bracket_id=bracket_id)


@app.get("/api/brackets/<bracket_id>")
def visitor_state(bracket_id):
    row, data = get_bracket(bracket_id)
    return jsonify(public_state(row, data))


@app.get("/api/owner/<bracket_id>/<token>")
def owner_state(bracket_id, token):
    row, data = get_bracket(bracket_id, owner=True)
    return jsonify(public_state(row, data, owner=True))


@app.post("/api/owner/<bracket_id>/<token>/settings")
def settings(bracket_id, token):
    body = request.get_json(silent=True) or {}
    field = body.get("field")
    value = body.get("value")
    if field not in ("published", "public_voting") or not isinstance(value, bool):
        return fail("Invalid setting.")
    with write_transaction() as connection:
        row, data = get_bracket(bracket_id, owner=True)
        if field == "public_voting":
            progressed = any(m["winner"] is not None for r in data["rounds"] for m in r)
            votes_exist = connection.execute("SELECT 1 FROM votes WHERE bracket_id=? LIMIT 1", (bracket_id,)).fetchone()
            if progressed or votes_exist or data["voting"]["phase"] != "idle":
                return fail("Voting mode cannot change after the bracket has started.")
        save_bracket(row, data, **{field: int(value)})
        connection.commit()
    return jsonify(ok=True)


@app.post("/api/owner/<bracket_id>/<token>/entries/<int:entry_id>/video")
def set_video(bracket_id, token, entry_id):
    video_id = str((request.get_json(silent=True) or {}).get("video_id", "")).strip()
    if video_id and not VIDEO_ID.fullmatch(video_id):
        return fail("Enter an 11-character YouTube video ID.")
    with write_transaction() as connection:
        row, data = get_bracket(bracket_id, owner=True)
        if not data["love_live"] or not 0 <= entry_id < len(data["entries"]):
            return fail("Entry not available.")
        entry = data["entries"][entry_id]
        if entry["matched"]:
            return fail("Matched song links cannot be replaced.")
        entry["video_id"] = video_id or None
        save_bracket(row, data)
        connection.commit()
    return jsonify(ok=True)


@app.post("/api/owner/<bracket_id>/<token>/winner")
def manual_winner(bracket_id, token):
    body = request.get_json(silent=True) or {}
    with write_transaction() as connection:
        row, data = get_bracket(bracket_id, owner=True)
        if row["public_voting"]:
            return fail("Use vote controls while public voting is enabled.")
        match = find_match(data, body.get("match_id"))
        if not match or match["a"] is None or match["b"] is None or body.get("choice") not in (match["a"], match["b"]):
            return fail("Choose an entry in a ready matchup.")
        match["winner"] = body["choice"]
        propagate(data)
        save_bracket(row, data)
        connection.commit()
    return jsonify(ok=True)


@app.post("/api/owner/<bracket_id>/<token>/vote-control")
def vote_control(bracket_id, token):
    body = request.get_json(silent=True) or {}
    action = body.get("action")
    with write_transaction() as connection:
        row, data = get_bracket(bracket_id, owner=True)
        if not row["public_voting"]:
            return fail("Enable public voting first.")
        voting = data["voting"]
        current = find_match(data, voting["current"])
        if action == "open" and voting["phase"] == "idle":
            if not row["published"]:
                return fail("Publish the bracket before opening a public vote.")
            current = current or next_match(data)
            if current is None:
                return fail("No matchup is ready.")
            voting.update(current=current["id"], phase="open")
        elif action == "close" and voting["phase"] == "open":
            voting["phase"] = "closed"
        elif action == "reveal" and voting["phase"] == "closed" and current:
            counts = vote_counts(bracket_id, current["id"])
            a_votes, b_votes = counts.get(current["a"], 0), counts.get(current["b"], 0)
            if a_votes == b_votes:
                choice = body.get("choice")
                if choice not in (current["a"], current["b"]):
                    return fail("Choose the winner for a tie or a vote with no ballots.")
            else:
                choice = current["a"] if a_votes > b_votes else current["b"]
            current["winner"] = choice
            propagate(data)
            voting["phase"] = "revealed"
        elif action == "advance" and voting["phase"] == "revealed":
            following = next_match(data)
            voting.update(current=following["id"] if following else None, phase="idle")
        else:
            return fail("That vote action is not available now.")
        save_bracket(row, data)
        connection.commit()
    return jsonify(ok=True)


@app.post("/api/brackets/<bracket_id>/vote")
def cast_vote(bracket_id):
    choice = (request.get_json(silent=True) or {}).get("choice")
    voter = request.cookies.get("bracketer_voter") or secrets.token_urlsafe(24)
    with write_transaction() as connection:
        row, data = get_bracket(bracket_id)
        voting = data["voting"]
        if not row["public_voting"] or voting["phase"] != "open":
            return fail("Voting is closed.")
        current = find_match(data, voting["current"])
        if current is None or choice not in (current["a"], current["b"]):
            return fail("Choose an entry in the open matchup.")
        try:
            connection.execute("INSERT INTO votes VALUES (?,?,?,?)", (bracket_id, current["id"], voter, choice))
        except sqlite3.IntegrityError:
            return fail("This browser has already voted in this matchup.", 409)
        connection.commit()
    response = jsonify(ok=True)
    response.set_cookie("bracketer_voter", voter, max_age=60 * 60 * 24 * 365, httponly=True, samesite="Lax", secure=request.is_secure)
    return response


@app.get("/api/brackets/<bracket_id>/events")
def events(bracket_id):
    get_bracket(bracket_id)

    def stream():
        last_version = None
        while True:
            connection = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True, timeout=10)
            try:
                row = connection.execute("SELECT version,published FROM brackets WHERE id=?", (bracket_id,)).fetchone()
            finally:
                connection.close()
            if row is None or not row[1]:
                yield "event: unpublished\ndata: {}\n\n"
                return
            if row[0] != last_version:
                last_version = row[0]
                yield f"data: {row[0]}\n\n"
            else:
                yield ": keepalive\n\n"
            time.sleep(1)

    return Response(stream(), mimetype="text/event-stream", headers={"X-Accel-Buffering": "no"})


@app.get("/api/brackets/<bracket_id>/qr.svg")
def qr_code(bracket_id):
    row, data = get_bracket(bracket_id)
    if not row["public_voting"]:
        abort(404)
    url = request.host_url.rstrip("/") + f"/vote/{bracket_id}"
    qr = qrcode.QRCode(border=2, box_size=5)
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
    output = io.BytesIO()
    image.save(output)
    return Response(output.getvalue(), mimetype="image/svg+xml")


if __name__ == "__main__":
    init_db()
    app.run(host=os.environ.get("BRACKETER_HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")))
