import hashlib
import importlib.util
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addons/service.actweeter/resources/lib"))
from smart_search_engine import CatalogSearch, LatestRequest, normalize, provider_path, unique_rows
from smart_search_sources import (Metadata, WatchedState, context, match_catalog_metadata,
                                  metadata_row, programmes, provider_children)


def store(path, rows):
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("CREATE TABLE items (stype TEXT,provider_id TEXT,title TEXT,norm TEXT,year TEXT,"
                   "poster TEXT,fanart TEXT,plot TEXT,genre TEXT,rating TEXT)")
        db.executemany("INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?)", [
            (kind, str(identity), title, normalize(title), year, "", "", "Una sinopsis", "", "")
            for kind, identity, title, year in rows])


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "provider_search_2.sqlite"
        store(self.path, [("movie", 1, "Máquina Guerra", "2017"),
                          ("movie", 2, "La máquina del tiempo", "2002"),
                          ("movie", 3, "Matrix", "1999"),
                          ("movie", 4, "Matrix Reloaded", "2003"),
                          ("series", 5, "La casa de papel", "2017"),
                          ("movie", 6, "[ES] Alien (1979) [4K]", "1979"),
                          ("movie", 7, "Dune", "1984"),
                          ("movie", 8, "Dune", "2021")])
        self.engine = CatalogSearch(self.path, 2)

    def tearDown(self):
        self.temp.cleanup()

    def test_canonical_title_finds_provider_missing_articles(self):
        self.assertEqual(self.engine.search("maquina de guerra")[0]["id"], "1")

    def test_metadata_matches_provider_title_missing_a_common_preposition(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO items VALUES ('movie','10','Gone Wind','gone wind','1939','','','','','')")
        rows = self.engine.match_metadata([dict(kind="movie", title="Gone with the Wind",
            tmdb_id="770", year="1939")])
        self.assertEqual([row["id"] for row in rows], ["10"])

    def test_accents_case_and_word_order(self):
        for query in ("MÁQUINA GUERRA", "guerra máquina", "maquina guerra"):
            with self.subTest(query=query):
                self.assertEqual(self.engine.search(query)[0]["id"], "1")

    def test_prefix_is_live_search(self):
        self.assertEqual(self.engine.search("casa pap")[0]["kind"], "series")

    def test_small_typo_and_exact_ranking(self):
        self.assertEqual(self.engine.search("matrx")[0]["id"], "3")
        self.assertEqual(self.engine.search("matrix")[0]["title"], "Matrix")

    def test_title_prefix_ranks_before_incidental_word(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO items VALUES ('movie','9','Generación Matrix','generacion matrix','2023','','','','','')")
        self.assertEqual([row["id"] for row in self.engine.search("matrix")], ["3", "4", "9"])

    def test_query_is_data_and_never_sql(self):
        self.assertEqual(self.engine.search("' OR 1=1; --"), [])
        self.assertEqual(len(self.engine.search("matrix")), 2)

    def test_empty_or_unknown_not_all_catalogue(self):
        self.assertEqual(self.engine.search(""), [])
        self.assertEqual(self.engine.search("zxqv unknown"), [])

    def test_canonical_metadata_maps_to_existing_provider_id(self):
        row = self.engine.match_metadata([dict(kind="movie", title="Máquina de guerra",
            tmdb_id="354287", year="2017", poster="https://image.tmdb.org/test.jpg")])[0]
        self.assertEqual(row["id"], "1")
        self.assertTrue(row["available"])
        self.assertIn("profile_num=2", row["path"])
        self.assertEqual(row["canonical_title"], "Máquina de guerra")

    def test_metadata_does_not_invent_availability(self):
        self.assertEqual(self.engine.match_metadata([dict(kind="movie", title="Alien Nation", year="1988")]), [])

    def test_remakes_keep_year_and_type(self):
        matches = self.engine.match_metadata([dict(kind="movie", title="Dune", year="2021")])
        self.assertEqual([row["id"] for row in matches], ["8"])
        self.assertEqual(self.engine.match_metadata([dict(kind="series", title="Dune", year="2021")]), [])

    def test_metadata_year_does_not_match_unknown_provider_year(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE items SET year='' WHERE provider_id='8'")
        self.assertEqual(self.engine.match_metadata([dict(kind="movie", title="Dune", year="2021")]), [])

    def test_technical_title_tags_and_original_titles(self):
        matches = self.engine.match_metadata([dict(kind="movie", title="Alien: el octavo pasajero",
                                                   originaltitle="Alien", year="1979")])
        self.assertEqual([row["id"] for row in matches], ["6"])

    def test_translated_alternative_title_keeps_verified_provider_identity(self):
        rows = self.engine.match_metadata([dict(kind="movie", title="War Machine", year="2017",
                                               aliases=["Máquina de guerra"], tmdb_id="354287")])
        self.assertEqual([row["id"] for row in rows], ["1"])
        self.assertIn("profile_num=2", rows[0]["path"])

    def test_alternative_title_of_different_year_is_not_available(self):
        self.assertEqual(self.engine.match_metadata([dict(kind="movie", title="War Machine", year="2026",
                                                        aliases=["Máquina de guerra"])]), [])

    def test_unknown_year_does_not_choose_between_remakes(self):
        self.assertEqual(self.engine.match_metadata([dict(kind="movie", title="Dune")]), [])

    def test_duplicate_editions_collapse_but_remakes_remain(self):
        rows = [dict(kind="movie", id="1", title="Matrix", year="1999"),
                dict(kind="movie", id="2", title="[ES] Matrix [4K]", year="1999"),
                dict(kind="movie", id="3", title="Matrix", year="2026")]
        self.assertEqual([row["id"] for row in unique_rows(rows)], ["1", "3"])

    def test_unknown_year_and_different_media_types_are_not_deduplicated(self):
        rows = [dict(kind="movie", id="1", title="Dune"), dict(kind="movie", id="2", title="Dune"),
                dict(kind="series", id="1", title="Dune")]
        self.assertEqual(len(unique_rows(rows)), 3)

    def test_profile_and_provider_ids_are_never_replaced_by_tmdb_ids(self):
        self.assertIn("id=1", self.engine.search("maquina guerra")[0]["path"])
        other = Path(self.temp.name) / "provider_search_3.sqlite"
        store(other, [("movie", 99, "Otra cuenta", "2020")])
        self.assertEqual(CatalogSearch(other, 3).search("maquina guerra"), [])

    def test_search_does_not_write_the_provider_database(self):
        before = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.engine.search("matrix")
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), before)

    def test_changed_snapshot_reloads_without_restart(self):
        self.engine.search("matrix")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM items WHERE provider_id='3'")
        self.assertNotIn("3", [row["id"] for row in self.engine.search("matrix")])


class WatchedStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / "watched_movies_p2.json"
        self.watched = WatchedState()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, data):
        self.path.write_text(json.dumps(data), encoding="utf-8")

    def test_exact_tmdb_movie_episode_season_and_show_keys(self):
        self.write({"tmdb:movie:42": True, "tmdb:episode:77:s1:e2": True,
                    "season:77:1": True, "tvshow:88": True})
        scope = (str(self.root), 2)
        for row in (dict(kind="movie", tmdb_id="42"),
                    dict(kind="episode", tmdb_show_id="77", season=1, episode=2)):
            with self.subTest(row=row):
                self.assertEqual(self.watched.badge(scope, row), "VISTO")

    def test_series_and_season_badges_require_complete_fresh_inventory(self):
        self.write({"tmdb:episode:77:s1:e1": True, "tmdb:episode:77:s1:e2": True})
        inventory = self.root / "series_changes_p2.json"
        inventory.write_text(json.dumps({"episode_inventory": {"900": {
            "complete": True, "checked_at": time.time(), "tmdb_id": "77",
            "episodes": [{"season": 1, "episode": 1, "provider_id": "a"},
                         {"season": 1, "episode": 2, "provider_id": "b"}]}}}))
        scope = (str(self.root), 2)
        self.assertEqual(self.watched.badge(scope,
            dict(kind="series", id="900", tmdb_id="77")), "VISTO")
        self.assertEqual(self.watched.badge(scope,
            dict(kind="season", id="900", tmdb_show_id="77", season=1)), "VISTO")
        payload = json.loads(inventory.read_text())
        payload["episode_inventory"]["900"]["episodes"].append(
            {"season": 1, "episode": 3, "provider_id": "c"})
        payload["episode_inventory"]["900"]["checked_at"] = time.time()
        inventory.write_text(json.dumps(payload))
        self.assertEqual(self.watched.badge(scope,
            dict(kind="series", id="900", tmdb_id="77")), "")
        self.assertEqual(self.watched.badge(scope,
            dict(kind="season", id="900", tmdb_show_id="77", season=1)), "")
        payload["episode_inventory"]["900"]["episodes"].pop()
        payload["episode_inventory"]["900"]["checked_at"] = time.time() - 15 * 86400
        inventory.write_text(json.dumps(payload))
        self.assertEqual(self.watched.badge(scope,
            dict(kind="series", id="900", tmdb_id="77")), "")
        self.assertEqual(self.watched.badge(scope,
            dict(kind="season", id="900", tmdb_show_id="77", season=1)), "")

    def test_series_level_marker_never_marks_future_episodes_complete(self):
        self.write({"tvshow:88": True, "tmdb:episode:77:s1:e2": True})
        self.assertEqual(self.watched.badge((str(self.root), 2),
                         dict(kind="series", id="900", tmdb_id="88")), "")

    def test_provider_movie_uses_only_its_exact_available_provider_id(self):
        self.write({"123": True})
        scope = (str(self.root), 2)
        self.assertEqual(self.watched.badge(scope, dict(kind="movie", id="123", available=True)), "VISTO")
        self.assertEqual(self.watched.badge(scope, dict(kind="movie", tmdb_id="42",
                         id="123", available=False)), "")

    def test_unique_exact_catalog_candidate_can_receive_tmdb_watch_badge(self):
        path = self.root / "provider_search_2.sqlite"
        store(path, [("movie", 123, "Chappie", "2015")])
        engine = CatalogSearch(path, 2)
        metadata = Mock()
        metadata.search.return_value = [dict(kind="movie", tmdb_id="198184", title="Chappie",
                                             year="2015")]
        matched, _ = match_catalog_metadata(engine, metadata, "Chappie", [])
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["id"], "123")
        self.assertEqual(matched[0]["tmdb_id"], "198184")
        self.write({"tmdb:movie:198663": True})
        self.assertEqual(self.watched.badge((str(self.root), 2), matched[0]), "")
        self.write({"tmdb:movie:198663": True, "tmdb:movie:198184": True})
        self.assertEqual(self.watched.badge((str(self.root), 2), matched[0]), "VISTO")
        metadata.search.assert_called_once_with("Chappie", "movie", "2015")
        metadata.search.reset_mock()
        cached, _ = match_catalog_metadata(CatalogSearch(path, 2), metadata, "Chappie", [])
        self.assertEqual(self.watched.badge((str(self.root), 2), cached[0]), "VISTO")
        metadata.search.assert_not_called()
        with closing(sqlite3.connect(path)) as db, db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            db.execute("UPDATE items SET title='Different Film',year='2016' WHERE provider_id='123'")
        self.assertNotIn("tmdb_id", CatalogSearch(path, 2).search("Different Film")[0])

    def test_title_year_fallback_handles_a_missing_provider_preposition(self):
        path = self.root / "provider_search_2.sqlite"
        store(path, [("movie", 123, "Gone Wind", "1939")])
        engine = CatalogSearch(path, 2)
        metadata = Mock()
        metadata.search.return_value = [dict(kind="movie", tmdb_id="770",
            title="Gone with the Wind", year="1939")]
        matched, _ = match_catalog_metadata(engine, metadata, "Gone Wind", [])
        self.assertEqual([(row["id"], row["tmdb_id"]) for row in matched], [("123", "770")])
        metadata.search.assert_called_once_with("Gone Wind", "movie", "1939")

    def test_initial_tmdb_result_is_remembered_for_offline_catalog_checks(self):
        path = self.root / "provider_search_2.sqlite"
        store(path, [("movie", 123, "Chappie", "2015")])
        metadata = Mock()
        matched, _ = match_catalog_metadata(CatalogSearch(path, 2), metadata, "Chappie",
            [dict(kind="movie", tmdb_id="198184", title="Chappie", year="2015")])
        self.assertEqual(matched[0]["tmdb_id"], "198184")
        metadata.search.assert_not_called()
        self.assertEqual(CatalogSearch(path, 2).search("Chappie")[0]["tmdb_id"], "198184")

    def test_catalog_fallback_does_not_query_without_a_four_digit_year(self):
        path = self.root / "provider_search_2.sqlite"
        store(path, [("movie", 123, "Chappie", "")])
        metadata = Mock()
        matched, _ = match_catalog_metadata(CatalogSearch(path, 2), metadata, "Chappie", [])
        self.assertEqual(matched, [])
        metadata.search.assert_not_called()

    def test_catalog_fallback_skips_ambiguous_remakes_and_cancelled_searches(self):
        path = self.root / "provider_search_2.sqlite"
        store(path, [("movie", 1, "Dune", "1984"), ("movie", 2, "Dune", "2021")])
        metadata = Mock()
        engine = CatalogSearch(path, 2)
        self.assertEqual(match_catalog_metadata(engine, metadata, "Dune", [])[0], [])
        self.assertEqual(match_catalog_metadata(engine, metadata, "Dune", [], lambda: False)[0], [])
        metadata.search.assert_not_called()

    def test_catalog_fallback_rejects_two_tmdb_ids_for_same_title_and_year(self):
        path = self.root / "provider_search_2.sqlite"
        store(path, [("movie", 123, "Chappie", "2015")])
        metadata = Mock()
        metadata.search.return_value = [dict(kind="movie", tmdb_id=tmdb_id,
            title="Chappie", year="2015") for tmdb_id in ("198184", "999999")]
        matched, _ = match_catalog_metadata(CatalogSearch(path, 2), metadata, "Chappie", [])
        self.assertEqual(matched, [])
        self.assertNotIn("tmdb_id", CatalogSearch(path, 2).search("Chappie")[0])

    def test_profile_scope_and_unverified_ids_fail_closed(self):
        self.write({"tmdb:movie:42": True})
        self.assertEqual(self.watched.badge((str(self.root), 1),
                         dict(kind="movie", tmdb_id="42")), "")
        self.assertEqual(self.watched.badge((str(self.root), 2),
                         dict(kind="movie", tmdb_id="0042x")), "")

    def test_changed_watch_store_is_reloaded_without_restart(self):
        self.write({})
        scope, row = (str(self.root), 2), dict(kind="movie", tmdb_id="42")
        self.assertEqual(self.watched.badge(scope, row), "")
        self.write({"tmdb:movie:42": True})
        self.assertEqual(self.watched.badge(scope, row), "VISTO")


class CatalogueSnapshotTests(CatalogueTests):
    def test_completed_snapshot_is_shared_without_second_catalogue_load(self):
        self.engine.refresh()
        view = self.engine.fork()
        self.assertIs(view.rows, self.engine.rows)
        self.assertIs(view.inverted, self.engine.inverted)
        self.assertIs(view.grams, self.engine.grams)
        with patch("smart_search_engine.readonly", side_effect=AssertionError("second title load")):
            view.refresh()

    def test_refresh_of_a_view_does_not_mutate_published_snapshot(self):
        self.engine.refresh()
        view = self.engine.fork()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM items WHERE provider_id='3'")
        view.refresh()
        self.assertTrue(any(row[1] == "3" for row in self.engine.rows))
        self.assertFalse(any(row[1] == "3" for row in view.rows))

    def test_invalid_playback_identity_rejected(self):
        for kind, identity, profile in (("movie", "x&password=bad", 1),
                                         ("person", "1", 1), ("movie", "1", 11)):
            with self.assertRaises(ValueError):
                provider_path(kind, identity, profile)


class SchedulingTests(unittest.TestCase):
    def test_latest_query_replaces_pending_jobs(self):
        jobs = LatestRequest()
        first = jobs.submit("m")
        jobs.submit("ma")
        last = jobs.submit("matrix")
        self.assertEqual(jobs.take(), (last, "matrix"))
        self.assertFalse(jobs.current(first))

    def test_cancel_during_resolution_invalidates_completion(self):
        jobs = LatestRequest()
        generation = jobs.submit("old")
        jobs.take()
        jobs.invalidate()
        self.assertFalse(jobs.current(generation))
        self.assertIsNone(jobs.pending)

    def test_closing_wakes_worker_and_discards_jobs(self):
        jobs, result = LatestRequest(), []
        worker = threading.Thread(target=lambda: result.append(jobs.take()))
        worker.start()
        jobs.close()
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result, [None])


class MetadataTests(unittest.TestCase):
    def test_alias_api_is_bounded_cached_and_does_not_extract_credentials(self):
        calls = []
        class API:
            def __init__(self, api_key):
                self.api_key = api_key
            def get_request_lc(self, kind, identity, route):
                calls.append((kind, identity, route))
                return {"titles": [{"title": "Máquina de guerra"}]}
        source = Metadata(Mock(), alias_api_key="0" * 32)
        rows = [dict(kind="movie", tmdb_id=str(n)) for n in range(8)]
        with patch.dict(sys.modules, {"tmdbbingiehelper_lib.api.tmdb.api": types.SimpleNamespace(TMDb=API)}):
            result = source.aliases(rows)
            self.assertEqual(len(calls), 3)
            self.assertEqual(result[0]["aliases"], ["Máquina de guerra"])
            source.aliases(rows[:3])
            self.assertEqual(len(calls), 3)
            source.aliases(rows, lambda: False)
            self.assertEqual(len(calls), 3)

    def test_aliases_without_own_key_do_not_import_helper_or_make_requests(self):
        rows = [dict(kind="movie", tmdb_id="603")]
        for key in ("", "not-an-api-key", "a\r\nb", None):
            source = Metadata(Mock(), alias_api_key=key)
            source.alias_api_factory = Mock(side_effect=AssertionError("no credential: no request"))
            self.assertEqual(source.aliases(rows), rows)
            source.alias_api_factory.assert_not_called()

    def test_alias_empty_error_response_is_not_cached_as_success_and_cools_down(self):
        clock = Mock(return_value=100)
        source = Metadata(Mock(), clock, alias_api_key="0" * 32)
        api = Mock()
        source.alias_api_factory = Mock(return_value=api)
        api.get_request_lc.return_value = {}
        rows = [dict(kind="movie", tmdb_id="603")]
        self.assertEqual(source.aliases(rows), rows)
        self.assertEqual(source.alias_cache, {})
        source.aliases(rows)
        self.assertEqual(api.get_request_lc.call_count, 1)
        clock.return_value = 111
        api.get_request_lc.return_value = {"titles": [{"title": "Matrix"}]}
        self.assertEqual(source.aliases(rows)[0]["aliases"], ["Matrix"])

    def test_details_do_not_replace_verified_playback_destination(self):
        source = Metadata(Mock())
        source._directory = Mock(return_value=[dict(kind="movie", tmdb_id="603", plot="Enriquecida",
                                                   path="plugin://metadata/play", available=False)])
        row = source.details(dict(kind="movie", id="99", tmdb_id="603", title="Matrix", available=True,
                                  path="plugin://plugin.video.xstream-pro/provider"))
        self.assertEqual(row["path"], "plugin://plugin.video.xstream-pro/provider")
        self.assertTrue(row["available"])
        self.assertEqual(row["plot"], "Enriquecida")

    def test_related_routes_preserve_cast_and_prioritize_directors(self):
        source = Metadata(Mock())
        source._directory = Mock(side_effect=[
            [dict(kind="person", tmdb_id="1", id="tmdb:1", title="Actor")],
            [dict(kind="person", tmdb_id="2", id="tmdb:2", title="Directora")]])
        rows = source.related(dict(kind="movie", tmdb_id="603", director=["Directora"]), "cast")
        self.assertEqual(rows[0]["subtitle"], "Dirección")
        self.assertEqual(rows[1]["subtitle"], "Reparto")
        self.assertEqual([c.args[0]["info"] for c in source._directory.call_args_list], ["cast", "crew"])

    def test_cancelled_related_routes_do_not_start_more_requests(self):
        source = Metadata(Mock())
        source._directory = Mock(side_effect=AssertionError("cancelled"))
        self.assertEqual(source.related(dict(kind="movie", tmdb_id="603"), "cast", lambda: False), [])

    def test_disabled_provider_does_not_read_its_profile_settings(self):
        factory, kodi = Mock(), Mock()
        kodi.getCondVisibility.return_value = False
        with self.assertRaises(ValueError):
            context(factory, Mock(), kodi)
        factory.assert_not_called()

    def test_uses_existing_helper_and_encodes_query(self):
        class Kodi:
            calls = []
            def executeJSONRPC(self, request):
                self.calls.append(json.loads(request))
                return json.dumps({"result": {"files": [{"title": "Tom Cruise", "plot": "Biografía",
                    "file": "plugin://plugin.video.tmdb.bingie.helper/?info=related&tmdb_type=person&tmdb_id=500",
                    "art": {"profile": "https://image.tmdb.org/person.jpg"}}]}})
        kodi = Kodi()
        source = Metadata(kodi)
        people = source.search("Tom Cruise & más")
        self.assertEqual(people[0]["kind"], "person")
        self.assertEqual(people[0]["plot"], "Biografía")
        self.assertIn("query=Tom+Cruise+%26+m%C3%A1s", kodi.calls[0]["params"]["directory"])
        source.search("Tom Cruise & más")
        self.assertEqual(len(kodi.calls), 1)
        self.assertEqual(kodi.calls[0]["method"], "Files.GetDirectory")

    def test_targeted_search_passes_media_type_and_year(self):
        source = Metadata(Mock())
        source._directory = Mock(return_value=[dict(kind="movie", tmdb_id="198184", year="2015")])
        self.assertEqual(source.search("Chappie", "movie", "2015")[0]["tmdb_id"], "198184")
        source._directory.assert_called_once_with({"info": "search", "tmdb_type": "movie",
                                                   "query": "Chappie", "year": "2015"})

    def test_untrusted_metadata_destination_is_rejected(self):
        self.assertIsNone(metadata_row({"file": "https://elsewhere/movie"}))
        self.assertIsNone(metadata_row({"file": "plugin://other/?tmdb_type=movie&tmdb_id=1"}))

    def test_failed_upstream_is_not_cached_as_success(self):
        class Kodi:
            def executeJSONRPC(self, request):
                return '{"error":{"code":-1}}'
        source = Metadata(Kodi())
        with self.assertRaises(RuntimeError):
            source.search("matrix")
        self.assertEqual(len(source.cache), 0)

    def test_failed_helper_has_bounded_retry_without_losing_cached_results(self):
        kodi = Mock()
        kodi.executeJSONRPC.return_value = '{"error":{"code":-1}}'
        clock = Mock(return_value=100)
        source = Metadata(kodi, clock)
        for query in ("matrix", "casa papel", "dune"):
            with self.assertRaises(RuntimeError):
                source.search(query)
        self.assertEqual(kodi.executeJSONRPC.call_count, 1)
        clock.return_value = 111
        with self.assertRaises(RuntimeError):
            source.search("matrix")
        self.assertEqual(kodi.executeJSONRPC.call_count, 2)

    def test_cancelled_person_credits_do_not_keep_requesting(self):
        class Kodi:
            def executeJSONRPC(self, _):
                raise AssertionError("cancelled job executed")
        self.assertEqual(Metadata(Kodi()).credits({"tmdb_id": "500"}, lambda: False), [])


class ProgrammeTests(unittest.TestCase):
    def test_obsolete_guide_query_does_not_open_databases(self):
        with patch("smart_search_sources.readonly") as opened:
            self.assertEqual(programmes("/missing", "noticias", current=lambda: False), [])
        opened.assert_not_called()
    def test_guide_readonly_and_hidden_locked_channels_excluded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with closing(sqlite3.connect(root / "TV46.db")) as db, db:
                db.execute("CREATE TABLE channels(idEpg,idChannel,sChannelName,sIconPath,bIsHidden,bIsLocked,bIsRadio,bEPGEnabled)")
                db.executemany("INSERT INTO channels VALUES (?,?,?,?,?,?,?,?)", [
                    (1, 11, "Canal de prueba", "", 0, 0, 0, 1),
                    (2, 12, "Oculto", "", 1, 0, 0, 1),
                    (3, 13, "Bloqueado", "", 0, 1, 0, 1)])
            with closing(sqlite3.connect(root / "Epg16.db")) as db, db:
                db.execute("CREATE TABLE epgtags(idBroadcast,idEpg,sTitle,sPlot,sIconPath,iStartTime,iEndTime,sCast,sDirector)")
                db.executemany("INSERT INTO epgtags VALUES (?,?,?,?,?,?,?,?,?)", [
                    (1, 1, "Máquina de guerra", "Programa", "", 900, 1100, "Brad Pitt", ""),
                    (2, 2, "Máquina de guerra", "", "", 900, 1100, "", ""),
                    (3, 3, "Máquina de guerra", "", "", 900, 1100, "", ""),
                    (4, 1, "Máquina de guerra", "Pasado", "", 700, 800, "", "")])
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            rows = programmes(root, "maquina guerra", now=1000)
            self.assertEqual([row["id"] for row in rows], ["1"])
            self.assertEqual(rows[0]["channel_id"], 11)
            self.assertTrue(rows[0]["live"])
            self.assertEqual(programmes(root, "brad pitt", now=1000)[0]["id"], "1")
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})

    def test_missing_guide_has_explicit_unavailable_state(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileNotFoundError):
                programmes(temp, "noticias")


class WindowContractTests(unittest.TestCase):
    def test_native_rows_keyboard_and_no_autoplay(self):
        path = ROOT / "addons/service.actweeter/resources/skins/Default/1080i/AcTweeteRSearch.xml"
        xml = ET.parse(path).getroot()
        controls = {node.get("id"): node for node in xml.iter("control") if node.get("id")}
        self.assertEqual(len(controls), len([n for n in xml.iter("control") if n.get("id")]))
        self.assertEqual(controls["100"].get("type"), "edit")
        self.assertEqual(controls["106"].get("type"), "button")
        self.assertEqual(controls["100"].findtext("visible"), "!System.Platform.Android")
        self.assertEqual(controls["106"].findtext("visible"), "System.Platform.Android")
        self.assertEqual(controls["106"].findtext("label"), "$INFO[Window.Property(search.query)]")
        self.assertNotIn("Control.GetLabel(100)", path.read_text())
        self.assertIn("String.IsEmpty(Window.Property(search.query))", path.read_text())
        # The edit control must not receive initial focus on Android.
        self.assertEqual(xml.findtext("defaultcontrol"), "103")
        self.assertIn('System.Platform.Android', (ROOT / "addons/service.actweeter/resources/lib/smart_search_ui.py").read_text())
        self.assertEqual(controls["5000"].get("type"), "grouplist")
        for number in range(5101, 5106):
            row = controls[str(number)]
            self.assertEqual(row.get("type"), "list")
            self.assertEqual(row.findtext("orientation"), "horizontal")
        self.assertEqual(controls["120"].findtext("orientation"), "vertical")
        self.assertNotIn("PlayMedia", path.read_text())
        self.assertNotIn("RunPlugin", path.read_text())

    def test_existing_menu_destination_launches_new_search(self):
        path = ROOT / "addons/skin.actweeter/1080i/Custom_1109_BingieSearch.xml"
        xml = ET.parse(path).getroot()
        self.assertEqual(xml.findtext("onload"), "RunScript(service.actweeter,smart_search)")
        self.assertNotIn("skinshortcuts-template", path.read_text())

    def test_facets_can_reach_first_visible_row_without_movies(self):
        xml = ET.parse(ROOT / "addons/service.actweeter/resources/skins/Default/1080i/AcTweeteRSearch.xml")
        for identity in range(111, 117):
            button = xml.find(".//control[@id='%d']" % identity)
            self.assertEqual([node.text for node in button.findall("ondown")],
                             [str(n) for n in range(5101, 5106)])
            self.assertTrue(all(node.get("condition") for node in button.findall("ondown")))


class WindowBehaviourTests(unittest.TestCase):
    def setUp(self):
        modules = {name: types.ModuleType(name) for name in ("xbmc", "xbmcaddon", "xbmcgui", "xbmcvfs")}
        modules["xbmcgui"].WindowXMLDialog = object
        modules["xbmcaddon"].Addon = Mock()
        spec = importlib.util.spec_from_file_location("search_ui_test",
            ROOT / "addons/service.actweeter/resources/lib/smart_search_ui.py")
        self.ui = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(self.ui)
        self.window = self.ui.SearchWindow.__new__(self.ui.SearchWindow)
        self.window.stop = threading.Event()
        self.window.rows = {control: [] for control in self.ui.ROWS}
        self.window.facet = "all"
        self.window.detail = None
        self.window.in_info = False
        self.window.info_can_launch = False
        self.window.info_close_requested = False
        self.window.suspended = False
        self.window.resume_positions = {}
        self.window.keyboard_focus_pending = False
        self.window.close = Mock()
        modules["xbmc"].Player = Mock(return_value=Mock(isPlayingVideo=Mock(return_value=False)))
        modules["xbmc"].executebuiltin = Mock()
        self.window.jobs, self.window.remote, self.window.epg_jobs = LatestRequest(), LatestRequest(), LatestRequest()
        self.window.history, self.window.person = [], None
        self.window.serial, self.window.query, self.window.scope = 0, "matrix", ("/catalogue", 1)
        self.window.getControl = Mock()
        self.window.getFocusId = Mock(return_value=5105)
        self.window.setFocusId = Mock()
        self.window.setProperty = Mock()
        self.window.getProperty = Mock(return_value="")
        self.window.getControl.return_value.getSelectedPosition.return_value = 0

    def test_watched_state_is_rendered_through_the_skin_badge(self):
        item = Mock()
        with patch.object(self.ui.xbmcgui, "ListItem", return_value=item, create=True):
            self.ui.listitem(dict(kind="movie", id="1", title="Film", tmdb_id="42"), "VISTO")
        properties = {call.args[0]: call.args[1] for call in item.setProperty.call_args_list}
        self.assertEqual(properties["search.watched"], "true")
        self.assertEqual(properties["search.badge"], "TMDb · VISTO")
        item.getVideoInfoTag.return_value.setPlaycount.assert_called_once_with(1)

    def test_episode_parent_tmdb_id_is_not_misreported_as_episode_identity(self):
        item = Mock()
        with patch.object(self.ui.xbmcgui, "ListItem", return_value=item, create=True):
            self.ui.listitem(dict(kind="episode", id="provider:9:1:2", title="Ep",
                                  tmdb_show_id="777", season=1, episode=2), "VISTO")
        item.getVideoInfoTag.return_value.setUniqueIDs.assert_not_called()

    def test_visible_android_query_tracks_text_and_clear_without_edit_focus(self):
        self.window._set_edit_text("Matrix")
        self.window.getControl.assert_called_with(100)
        self.window.getControl.return_value.setText.assert_called_with("Matrix")
        self.window.setProperty.assert_called_with("search.query", "Matrix")
        self.window._set_edit_text("")
        self.window.getControl.return_value.setText.assert_called_with("")
        self.window.setProperty.assert_called_with("search.query", "")
        self.window.setFocusId.assert_not_called()

    def test_local_worker_executes_query_and_publishes_shared_snapshot(self):
        self.window.jobs = Mock()
        self.window.jobs.take.side_effect = [(1, (0, "matrix", self.window.scope)), None]
        self.window.jobs.current.return_value = True
        engine = Mock()
        engine.search.return_value = [dict(kind="movie", id="1", title="Matrix")]
        self.window._post = Mock()
        with patch.object(self.ui, "catalogue", return_value=engine):
            self.window._local_worker()
        engine.search.assert_called_once_with("matrix")
        self.assertEqual(self.window._post.call_args.args[1], "local")
        self.assertIs(self.window.shared_index, engine.fork.return_value)

    def test_provider_navigation_uses_metadata_worker_not_local_query_worker(self):
        self.window.remote = Mock()
        subject = dict(kind="series", id="99", title="Serie", _section="provider")
        self.window.remote.take.side_effect = [(1, (0, "matrix", self.window.scope, subject)), None]
        self.window.remote.current.return_value = True
        self.window._post = Mock()
        with patch.object(self.ui, "provider_children", return_value=[]) as children:
            self.window._metadata_worker()
        children.assert_called_once_with(self.ui.xbmc, subject, self.window.scope)
        self.window._post.assert_called_once_with(0, "children", [])

    def test_nested_person_navigation_restores_results_and_query_without_fetching(self):
        movie = dict(kind="movie", id="99", title="Matrix", available=True)
        person = dict(kind="person", id="tmdb:6384", title="Keanu Reeves", tmdb_id="6384")
        self.window.rows[5101] = [movie]
        with patch.object(self.ui, "listitem", side_effect=lambda row, *_args: row):
            self.window._browse(dict(movie, tmdb_id="603"), "cast")
            self.window.rows[5104] = [person]
            self.window._browse(person)
            self.window._back()
            self.assertEqual(self.window.rows[5104], [person])
            self.window.setProperty.assert_any_call("search.status", "Explorando · Matrix")
            self.window._back()
        self.assertEqual(self.window.rows[5101], [movie])
        self.assertEqual(self.window.query, "matrix")
        self.assertIsNone(self.window.person)
        self.assertEqual(self.window.history, [])
        self.window.setProperty.assert_any_call("search.status", "Resultados · matrix")

    def test_info_enrichment_keeps_focus_on_the_current_button(self):
        self.window._show_detail(dict(kind="movie", title="Matrix", id="99", available=True), remember=False)
        self.window.setFocusId.assert_not_called()

    def test_provider_browse_labels_do_not_claim_related_titles_or_old_query_counts(self):
        self.window._browse(dict(kind="series", id="99", title="Serie"), "provider")
        self.window.setProperty.assert_any_call("search.hero.plot", "Temporadas y episodios del proveedor")
        self.window.setProperty.assert_any_call("search.status", "Explorando · Serie")

    def test_metadata_arrival_keeps_selected_provider_item(self):
        self.window.rows[5101] = [{"kind": "movie", "id": "1"}, {"kind": "movie", "id": "2"}]
        listing = self.window.getControl.return_value
        listing.getSelectedPosition.return_value = 1
        with patch.object(self.ui, "listitem", side_effect=lambda row, *_args: row):
            self.window._fill(5101, [{"kind": "movie", "id": "2"}, {"kind": "movie", "id": "1"}])
        listing.selectItem.assert_called_once_with(0)

    def test_unchanged_rows_do_not_rebuild_the_container(self):
        self.window.rows[5101] = [{"kind": "movie", "id": "1"}]
        self.window._fill(5101, [{"kind": "movie", "id": "1"}])
        self.window.getControl.assert_not_called()

    def test_detail_returns_to_original_result_row(self):
        self.window._show_detail({"kind": "person", "title": "Persona"})
        self.window.onClick(702)
        self.window.setFocusId.assert_called_with(5105)
        self.assertIsNone(self.window.detail)

    def test_overlay_does_not_dispatch_clicks_to_underlying_results(self):
        self.window.detail = {"title": "Biografía"}
        self.window.onClick(5101)
        self.window.getControl.assert_not_called()

    def test_available_result_opens_info_not_playback(self):
        self.window.rows[5101] = [{"kind": "movie", "id": "1", "title": "Matrix", "available": True}]
        self.window.getControl.return_value.getSelectedPosition.return_value = 0
        dialog = Mock()
        with patch.object(self.ui.xbmcgui, "Dialog", return_value=dialog, create=True), \
             patch.object(self.ui, "listitem", return_value="selected-item"), \
             patch.object(self.ui, "context", return_value=self.window.scope):
            self.window.onClick(5101)
            dialog.info.assert_not_called()
            self.window.onClick(701)
        dialog.info.assert_called_once_with("selected-item")
        self.assertFalse(self.window.in_info)
        self.assertFalse(self.window.suspended)
        self.window.close.assert_not_called()

    def test_native_info_playback_suspends_search_without_stopping_the_player(self):
        self.window.detail = dict(kind="movie", title="Matrix", id="1", available=True)
        self.ui.xbmc.Player.return_value.isPlayingVideo.side_effect = [False, True]
        dialog = Mock()
        with patch.object(self.ui.xbmcgui, "Dialog", return_value=dialog, create=True), \
             patch.object(self.ui, "listitem", return_value="selected-item"), \
             patch.object(self.ui, "context", return_value=self.window.scope):
            self.window.onClick(701)
        self.assertTrue(self.window.suspended)
        self.window.close.assert_called_once()
        self.assertFalse(self.window.stop.is_set())
        self.ui.xbmc.executebuiltin.assert_called_once_with("ActivateWindow(fullscreenvideo)")
        self.ui.xbmc.Player.return_value.stop.assert_not_called()

    def test_playback_return_restores_query_rows_and_selection_without_new_workers(self):
        self.window.ready = self.window.suspended = True
        self.window.detail = dict(kind="movie", title="Matrix")
        self.window.rows[5101] = [dict(kind="movie", id="1", title="Matrix")]
        self.window.resume_positions = {5101: 0}
        with patch.object(self.ui, "listitem", side_effect=lambda row, *_args: row), \
             patch.object(self.ui.xbmcgui, "ListItem", create=True), \
             patch.object(self.ui.threading, "Thread") as thread:
            self.window.onInit()
        self.assertFalse(self.window.suspended)
        self.assertEqual(self.window.rows[5101][0]["title"], "Matrix")
        self.window.getControl.return_value.setText.assert_called_once_with("matrix")
        self.window.setFocusId.assert_called_with(701)
        thread.assert_not_called()

    def test_info_playback_closes_modal_once_but_never_stops_content(self):
        self.window.in_info = self.window.info_can_launch = True
        self.ui.xbmc.Player.return_value.isPlayingVideo.return_value = True
        self.window._handoff_info_playback()
        self.window._handoff_info_playback()
        self.ui.xbmc.executebuiltin.assert_called_once_with("Dialog.Close(movieinformation)")
        self.ui.xbmc.Player.return_value.stop.assert_not_called()

    def test_preexisting_video_does_not_trigger_info_playback_handoff(self):
        self.window.in_info = True
        self.ui.xbmc.Player.return_value.isPlayingVideo.return_value = True
        self.window._handoff_info_playback()
        self.ui.xbmc.executebuiltin.assert_not_called()

    def test_qwerty_focus_waits_for_actual_control_visibility_not_a_timer(self):
        self.window.getProperty.return_value = "false"
        self.window.onClick(103)
        self.assertTrue(self.window.keyboard_focus_pending)
        self.window.setFocusId.assert_called_with(103)
        self.ui.xbmc.getCondVisibility = Mock(return_value=False)
        self.window._focus_keyboard_if_ready()
        self.window.setFocusId.assert_called_with(103)
        self.ui.xbmc.getCondVisibility.return_value = True
        self.window._focus_keyboard_if_ready()
        self.assertFalse(self.window.keyboard_focus_pending)
        self.window.setFocusId.assert_called_with(120)

    def test_back_cancels_pending_qwerty_focus(self):
        self.window.keyboard_focus_pending = True
        self.window.getProperty.return_value = "true"
        self.window._back()
        self.assertFalse(self.window.keyboard_focus_pending)
        self.window.setFocusId.assert_called_with(100)

    def test_changed_profile_cannot_open_old_playback_item(self):
        self.window.detail = dict(kind="movie", title="Matrix", id="99", available=True)
        with patch.object(self.ui, "context", return_value=("/another-profile", 2)), \
             patch.object(self.ui.xbmcgui, "Dialog", create=True) as dialog:
            self.window.onClick(701)
        dialog.assert_not_called()


class ProviderBrowseTests(unittest.TestCase):
    def test_seasons_use_returned_profile_bound_routes(self):
        parent = dict(path="plugin://plugin.video.xstream-pro/?mode=xtream_series&series_id=99&profile_num=2")
        response = {"files": [dict(label="Temporada 1", file="plugin://plugin.video.xstream-pro/?mode=xtream_season&series_id=99&profile_num=2&season_num=1"),
                              dict(label="Otro perfil", file="plugin://plugin.video.xstream-pro/?mode=xtream_season&series_id=99&profile_num=3&season_num=1")]}
        with patch("smart_search_sources.rpc", return_value=response):
            rows = provider_children(Mock(), parent, ("/profile", 2))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "season")
        self.assertEqual(rows[0]["season"], 1)

    def test_duplicate_episode_sources_collapse_without_inventing_urls(self):
        parent = dict(path="plugin://plugin.video.xstream-pro/?mode=xtream_season&series_id=99&profile_num=2&season_num=1",
                      tmdb_id="777")
        path = "plugin://plugin.video.xstream-pro/?mode=source_select&tmdb_type=tv&season=1&episode=2&title=Episode"
        result = {"files": [dict(label="Episodio", file=path)] * 2 + [dict(label="Externo", file="https://example.test/play")]}
        with patch("smart_search_sources.rpc", return_value=result):
            rows = provider_children(Mock(), parent, ("/profile", 2))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["path"], path)
        self.assertEqual(rows[0]["kind"], "episode")
        self.assertEqual(rows[0]["tmdb_show_id"], "777")
        self.assertNotIn("tmdb_id", rows[0])

    def test_invalid_parent_is_rejected_before_kodi_request(self):
        with patch("smart_search_sources.rpc") as request:
            for path in ("https://example.test/", "plugin://other/?mode=xtream_series",
                         "plugin://plugin.video.xstream-pro/?mode=xtream_series&series_id=99&profile_num=3"):
                with self.assertRaises(ValueError):
                    provider_children(Mock(), dict(path=path), ("/profile", 2))
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
