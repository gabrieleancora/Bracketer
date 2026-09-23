import importlib
import os
import tempfile
import unittest
from pathlib import Path


class BracketFlowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        os.environ["BRACKETER_DB"] = str(Path(self.temp.name) / "test.sqlite3")
        import app
        self.app_module = importlib.reload(app)
        self.client = self.app_module.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def create(self, names=None, love_live=False):
        response = self.client.post('/api/brackets', json={
            'title': 'Test bracket', 'names': names or ['A', 'B', 'C', 'D'],
            'love_live': love_live,
        })
        self.assertEqual(response.status_code, 201)
        owner_url = response.json['owner_url']
        parts = owner_url.split('/')
        return parts[2], parts[3]

    def owner(self, bracket_id, token):
        return self.client.get(f'/api/owner/{bracket_id}/{token}').json

    def test_private_draft_publication_manual_progress_and_owner_protection(self):
        bracket_id, token = self.create()
        initial = self.owner(bracket_id, token)
        self.assertEqual(sorted(value for match in initial['rounds'][0] for value in (match['a'], match['b'])), [0, 1, 2, 3])
        self.assertEqual([len(round_matches) for round_matches in initial['rounds']], [2, 1])
        public_url = f'/api/brackets/{bracket_id}'
        self.assertEqual(self.client.get(public_url).status_code, 404)
        self.assertEqual(self.client.post(f'/api/owner/{bracket_id}/wrong/winner', json={}).status_code, 404)
        self.client.post(f'/api/owner/{bracket_id}/{token}/settings', json={'field':'published','value':True})
        self.assertEqual(self.client.get(public_url).status_code, 200)
        self.assertIn(b'<svg', self.client.get(f'/api/owner/{bracket_id}/{token}/qr.svg').data)
        first = self.owner(bracket_id, token)['rounds'][0][0]
        self.assertEqual(self.client.post(f'/api/owner/{bracket_id}/{token}/winner', json={'match_id':first['id'],'choice':first['a']}).status_code, 200)
        self.assertEqual(self.owner(bracket_id, token)['rounds'][1][0]['a'], first['a'])
        self.assertEqual(self.client.post(f'/api/owner/{bracket_id}/{token}/winner', json={'match_id':first['id'],'choice':first['b']}).status_code, 200)
        self.assertEqual(self.owner(bracket_id, token)['rounds'][1][0]['a'], first['b'])
        self.client.post(f'/api/owner/{bracket_id}/{token}/settings', json={'field':'published','value':False})
        self.assertEqual(self.client.get(public_url).status_code, 404)

    def test_voting_sequence_and_single_browser_ballot(self):
        bracket_id, token = self.create(['A', 'B'])
        settings = f'/api/owner/{bracket_id}/{token}/settings'
        controls = f'/api/owner/{bracket_id}/{token}/vote-control'
        self.assertEqual(self.client.post(settings, json={'field':'public_voting','value':True}).status_code, 200)
        self.assertEqual(self.client.post(controls, json={'action':'open'}).status_code, 400)
        self.client.post(settings, json={'field':'published','value':True})
        self.assertEqual(self.client.post(controls, json={'action':'open'}).status_code, 200)
        match = self.owner(bracket_id, token)['rounds'][0][0]
        vote = f'/api/brackets/{bracket_id}/vote'
        self.assertEqual(self.client.post(vote, json={'choice':match['a']}).status_code, 200)
        self.assertTrue(self.client.get(f'/api/brackets/{bracket_id}').json['has_voted'])
        self.assertEqual(self.client.post(vote, json={'choice':match['b']}).status_code, 409)
        self.assertNotIn('counts', self.client.get(f'/api/brackets/{bracket_id}').json)
        self.assertEqual(self.client.post(controls, json={'action':'close'}).status_code, 200)
        self.assertEqual(self.client.post(vote, json={'choice':match['b']}).status_code, 400)
        self.assertEqual(self.client.post(controls, json={'action':'reveal'}).status_code, 200)
        self.assertEqual(self.owner(bracket_id, token)['rounds'][0][0]['winner'], match['a'])
        self.assertEqual(self.client.post(controls, json={'action':'advance'}).status_code, 200)
        self.assertIsNone(self.owner(bracket_id, token)['voting']['current'])

    def test_tie_requires_owner_choice_and_song_lookup(self):
        bracket_id, token = self.create(['Bokura no LIVE Kimi to no LIFE', 'Unknown song'], love_live=True)
        state = self.owner(bracket_id, token)
        self.assertEqual(state['entries'][0]['video_id'], 'YIgoFjO9Mg4')
        self.assertTrue(state['entries'][0]['matched'])
        self.assertIsNone(state['entries'][1]['video_id'])
        video_url = f'/api/owner/{bracket_id}/{token}/entries/1/video'
        self.assertEqual(self.client.post(video_url, json={'video_id':'abcdefghijk'}).status_code, 200)
        self.assertEqual(self.client.post(f'/api/owner/{bracket_id}/{token}/entries/0/video', json={'video_id':'abcdefghijk'}).status_code, 400)
        settings = f'/api/owner/{bracket_id}/{token}/settings'
        controls = f'/api/owner/{bracket_id}/{token}/vote-control'
        self.client.post(settings, json={'field':'public_voting','value':True})
        self.client.post(settings, json={'field':'published','value':True})
        self.client.post(controls, json={'action':'open'})
        self.client.post(controls, json={'action':'close'})
        self.assertEqual(self.client.post(controls, json={'action':'reveal'}).status_code, 400)
        match = self.owner(bracket_id, token)['rounds'][0][0]
        self.assertEqual(self.client.post(controls, json={'action':'reveal','choice':match['b']}).status_code, 200)
        self.assertEqual(self.owner(bracket_id, token)['rounds'][0][0]['winner'], match['b'])


if __name__ == '__main__':
    unittest.main()
