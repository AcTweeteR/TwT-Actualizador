import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'addons/service.actweeter/resources'))
from lib.trakt_watched_reconcile import remote_watched_status

class TestWatchedReconcile(unittest.TestCase):
 def test_same_content_with_additional_ids_not_reposted(self):
  remote=dict(complete=True,account='owner',records={'movie:tmdb:42':dict(identity=dict(kind='movie',ids={'tmdb':'42','imdb':'tt0000042'}),watched_at='2026-11-05T11:00:00Z')})
  self.assertEqual(remote_watched_status(remote,dict(kind='movie',ids={'imdb':'tt0000042'}),account='owner'),'watched')
  self.assertEqual(remote_watched_status(remote,dict(kind='movie',ids={'tmdb':'42'}),account='owner'),'watched')
  self.assertEqual(remote_watched_status(remote,dict(kind='movie',ids={'tmdb':'43'}),account='owner'),'missing')
  self.assertEqual(remote_watched_status(remote,dict(kind='movie',ids={'tmdb':'42','imdb':'tt0000043'}),account='owner'),'conflict')
  self.assertEqual(remote_watched_status(remote,dict(kind='movie',ids={'tmdb':'42'}),account='other'),'unverified')
 def test_episode_coordinates_and_complete_evidence(self):
  remote=dict(complete=True,account='owner',records={'one':dict(identity=dict(kind='episode',ids={'tmdb':'99','tvdb':'101'},season=2,episode=1),watched_at='2026-11-05T11:00:00Z')})
  self.assertEqual(remote_watched_status(remote,dict(kind='episode',ids={'tvdb':'101'},season=2,episode=1),account='owner'),'watched')
  self.assertEqual(remote_watched_status(remote,dict(kind='episode',ids={'tvdb':'101'},season=2,episode=2),account='owner'),'missing')
  self.assertEqual(remote_watched_status(dict(remote,complete=False),dict(kind='episode',ids={'tvdb':'101'},season=2,episode=1),account='owner'),'unverified')
  self.assertEqual(remote_watched_status(dict(remote,records={'bad': {'identity': {}}}),dict(kind='episode',ids={'tvdb':'101'},season=2,episode=1),account='owner'),'unverified')
if __name__=='__main__':unittest.main()
