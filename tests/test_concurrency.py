import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import test_app


class ConcurrentWritesTest(unittest.TestCase):
    setUp = test_app.BracketFlowTest.setUp
    tearDown = test_app.BracketFlowTest.tearDown
    create = test_app.BracketFlowTest.create
    owner = test_app.BracketFlowTest.owner

    def run_race(self, first, second):
        entered = threading.Event()
        release = threading.Event()
        original = self.app_module.get_bracket

        def paused_get(*args, **kwargs):
            result = original(*args, **kwargs)
            if not entered.is_set():
                entered.set()
                if not release.wait(5):
                    raise TimeoutError("first request was not released")
            return result

        with patch.object(self.app_module, "get_bracket", paused_get):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first_result = pool.submit(first)
                self.assertTrue(entered.wait(5))
                # The second request starts while the first still owns the write lock.
                second_result = pool.submit(second)
                time.sleep(0.05)
                release.set()
                return first_result.result(timeout=15), second_result.result(timeout=15)

    def test_owner_edits_preserve_both_changes(self):
        bracket_id, token = self.create()
        url = f"/api/owner/{bracket_id}/{token}/settings"

        def change(field):
            with self.app_module.app.test_client() as client:
                return client.post(url, json={"field": field, "value": True}).status_code

        results = self.run_race(lambda: change("published"), lambda: change("public_voting"))
        self.assertEqual(results, (200, 200))
        state = self.owner(bracket_id, token)
        self.assertTrue(state["published"])
        self.assertTrue(state["public_voting"])
        self.assertEqual(state["version"], 3)

    def test_vote_accepted_before_close_is_counted(self):
        bracket_id, token = self.create(["A", "B"])
        base = f"/api/owner/{bracket_id}/{token}"
        self.client.post(base + "/settings", json={"field": "public_voting", "value": True})
        self.client.post(base + "/settings", json={"field": "published", "value": True})
        self.client.post(base + "/vote-control", json={"action": "open"})
        match = self.owner(bracket_id, token)["rounds"][0][0]

        def vote():
            with self.app_module.app.test_client() as client:
                return client.post(f"/api/brackets/{bracket_id}/vote", json={"choice": match["a"]}).status_code

        def close():
            with self.app_module.app.test_client() as client:
                return client.post(base + "/vote-control", json={"action": "close"}).status_code

        self.assertEqual(self.run_race(vote, close), (200, 200))
        self.assertEqual(self.owner(bracket_id, token)["counts"], {str(match["a"]): 1})
        self.assertEqual(self.client.post(base + "/vote-control", json={"action": "reveal"}).status_code, 200)
        self.assertEqual(self.owner(bracket_id, token)["rounds"][0][0]["winner"], match["a"])

    def test_vote_after_close_is_rejected(self):
        bracket_id, token = self.create(["A", "B"])
        base = f"/api/owner/{bracket_id}/{token}"
        self.client.post(base + "/settings", json={"field": "public_voting", "value": True})
        self.client.post(base + "/settings", json={"field": "published", "value": True})
        self.client.post(base + "/vote-control", json={"action": "open"})
        match = self.owner(bracket_id, token)["rounds"][0][0]

        def close():
            with self.app_module.app.test_client() as client:
                return client.post(base + "/vote-control", json={"action": "close"}).status_code

        def vote():
            with self.app_module.app.test_client() as client:
                return client.post(f"/api/brackets/{bracket_id}/vote", json={"choice": match["a"]}).status_code

        self.assertEqual(self.run_race(close, vote), (200, 400))
        self.assertEqual(self.owner(bracket_id, token)["counts"], {})
