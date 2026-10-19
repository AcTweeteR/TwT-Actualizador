"""Trailer lookup must never treat episode identifiers as movie/show IDs."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/service.actweeter/resources/lib"))
from slyguy_preview_bridge import _identity, _REQUEST_ID, preview_source, preview_target
from kodi_auto_preview import read_preview_metadata
from test_kodi_auto_preview_notifications import coordinator, FakeKodi, focus_packet


class SeriesPreviewTests(unittest.TestCase):
    def test_provider_request_id_cannot_escape_temp_manifest(self):
        self.assertIsNotNone(_REQUEST_ID.fullmatch("a" * 32 + "-12"))
        for value in ("../../userdata", "a" * 32 + "-0", "a" * 32 + "-1/../../x", "", "bad"):
            with self.subTest(value=value):
                self.assertIsNone(_REQUEST_ID.fullmatch(value))

    def test_provider_identity_rejects_missing_or_non_string_ids(self):
        for value in (None, 123, False, "", "../unsafe", "１２３"):
            with self.subTest(value=value):
                self.assertEqual(_identity({"tmdb": value}), "")
        self.assertEqual(_identity({"tmdb": "123"}), "tmdb:123")

    def test_imdb_route_cannot_be_misread_as_youtube_id(self):
        def forbidden(path):
            self.fail("IMDb must not be passed to the YouTube extractor")
        self.assertEqual(preview_target(
            "plugin://slyguy.trailers/imdb/?video_id=tt1234567", forbidden),
            ("imdb", "tt1234567"))
        self.assertEqual(preview_target(
            "plugin://other.addon/play/?video_id=tt1234567", forbidden), ("", ""))
        self.assertEqual(preview_target(
            "plugin://slyguy.trailers/play/?video_id=abc_def-123", forbidden),
            ("youtube", "abc_def-123"))

    def test_movie_and_show_use_native_slyguy_types(self):
        for media in ("movie", "tvshow"):
            with self.subTest(media=media):
                source = preview_source(dict(media_type=media, title="Title", tmdb="123"))
                self.assertEqual(source["mediatype"], media)
                self.assertEqual(source["unique_ids"], {"tmdb": "123"})
                bridge = coordinator(FakeKodi())
                self.assertTrue(bridge._focus(focus_packet(media_type=media)))
                self.assertEqual(bridge.item_data[bridge.scheduler.latest.generation]["media_type"], media)

    def test_series_hub_is_an_eligible_preview_surface(self):
        bridge = coordinator(FakeKodi())
        self.assertTrue(bridge._focus(focus_packet(media_type="tvshow", window=11110)))
        self.assertEqual(bridge.scheduler.latest.window, 11110)

    def test_episode_and_season_resolve_only_parent_identity(self):
        for media in ("episode", "season"):
            with self.subTest(media=media):
                source = preview_source(dict(media_type=media, title="Episode", tmdb="999",
                    imdb="tt999", dbid="99", show_title="Series", show_tmdb="123", show_year="2020"))
                self.assertEqual(source["mediatype"], "tvshow")
                self.assertEqual(source["title"], "Series")
                self.assertEqual(source["unique_ids"], {"tmdb": "123"})
                self.assertEqual(source["dbid"], -1)

    def test_missing_parent_identity_does_not_fall_back_to_episode_id(self):
        self.assertIsNone(preview_source(dict(media_type="episode", title="Episode",
            show_title="Series", tmdb="999", imdb="tt999", dbid="99")))
        self.assertIsNone(preview_source(dict(media_type="channel", tmdb="1")))

    def test_library_episode_uses_parent_database_identity(self):
        source = preview_source(dict(media_type="episode", show_title="Series", show_dbid="7"))
        self.assertEqual(source["dbid"], "7")
        self.assertEqual(source["unique_ids"], {})

    def test_xstream_resume_parent_properties_are_explicit(self):
        class Kodi:
            def getInfoLabel(self, label):
                return {"ListItem.DBType": "episode", "ListItem.UniqueID(tmdb)": "999",
                    "ListItem.Property(XStream.ProviderOnly)": "true",
                    "ListItem.Property(tmdb_id)": "123", "ListItem.TVShowTitle": "Series"}.get(label, "")
        source = preview_source(read_preview_metadata(Kodi(), "ListItem."))
        self.assertEqual(source["unique_ids"], {"tmdb": "123"})


if __name__ == "__main__":
    unittest.main()
