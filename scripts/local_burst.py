"""Exercise concurrent ballot writes in process; this is not a WSGI capacity test."""

import argparse
import importlib
import os
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(attendees):
    with tempfile.TemporaryDirectory() as directory:
        os.environ["BRACKETER_DB"] = str(Path(directory) / "burst.sqlite3")
        import app
        module = importlib.reload(app)
        module.init_db()
        owner = module.app.test_client()
        created = owner.post("/api/brackets", json={"title": "Burst", "names": ["A", "B"]})
        assert created.status_code == 201, created.json
        owner_url = created.json["owner_url"]
        bracket_id = owner_url.split("/")[2]
        api = f"/api{owner_url}"
        for field in ("public_voting", "published"):
            response = owner.post(api + "/settings", json={"field": field, "value": True})
            assert response.status_code == 200, response.json
        response = owner.post(api + "/vote-control", json={"action": "open"})
        assert response.status_code == 200, response.json
        choice = owner.get(api).json["rounds"][0][0]["a"]
        start = threading.Event()

        def vote():
            with module.app.test_client() as client:
                start.wait()
                result = client.post(f"/api/brackets/{bracket_id}/vote", json={"choice": choice})
                return result.status_code, time.perf_counter() - released

        with ThreadPoolExecutor(max_workers=attendees) as pool:
            futures = [pool.submit(vote) for _ in range(attendees)]
            released = time.perf_counter()
            start.set()
            results = [future.result(timeout=30) for future in futures]
        close = owner.post(api + "/vote-control", json={"action": "close"})
        assert close.status_code == 200, close.json
        count = owner.get(api).json["counts"].get(str(choice), 0)
        statuses = {status: sum(result[0] == status for result in results) for status, _ in results}
        latencies = sorted(duration for _, duration in results)
        p95 = latencies[int(0.95 * (len(latencies) - 1))]
        p99 = latencies[int(0.99 * (len(latencies) - 1))]
        print(f"{attendees} attendees: statuses={statuses}, durable_ballots={count}, "
              f"elapsed={time.perf_counter() - released:.3f}s, "
              f"p95={p95:.3f}s, p99={p99:.3f}s")
        if statuses != {200: attendees} or count != attendees:
            raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attendees", type=int, choices=(200, 300))
    run(parser.parse_args().attendees)
