import hashlib
import importlib.util
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addons/service.actweeter/resources/lib"))
from smart_search_engine import CatalogSearch, LatestRequest, normalize, provider_path
from smart_search_sources import Metadata, context, metadata_row, programmes


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

    def test_accents_case_and_word_order(self):
        for query in ("MÁQUINA GUERRA", "guerra máquina", "maquina guerra"):
            with self.subTest(query=query):
                self.assertEqual(self.engine.search(query)[0]["id"], "1")

    def test_prefix_is_live_search(self):
        self.assertEqual(self.engine.search("casa pap")[0]["kind"], "series")

    def test_small_typo_and_exact_ranking(self):
        self.assertEqual(self.engine.search("matrx")[0]["id"], "3")
        self.assertEqual(self.engine.search("matrix")[0]["title"], "Matrix")

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

    def test_cancelled_person_credits_do_not_keep_requesting(self):
        class Kodi:
            def executeJSONRPC(self, _):
                raise AssertionError("cancelled job executed")
        self.assertEqual(Metadata(Kodi()).credits({"tmdb_id": "500"}, lambda: False), [])


class ProgrammeTests(unittest.TestCase):
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
        self.window.getControl = Mock()
        self.window.getFocusId = Mock(return_value=5105)
        self.window.setFocusId = Mock()
        self.window.setProperty = Mock()

    def test_metadata_arrival_keeps_selected_provider_item(self):
        self.window.rows[5101] = [{"id": "1"}, {"id": "2"}]
        listing = self.window.getControl.return_value
        listing.getSelectedPosition.return_value = 1
        with patch.object(self.ui, "listitem", side_effect=lambda row: row):
            self.window._fill(5101, [{"id": "2"}, {"id": "1"}])
        listing.selectItem.assert_called_once_with(0)

    def test_unchanged_rows_do_not_rebuild_the_container(self):
        self.window.rows[5101] = [{"id": "1"}]
        self.window._fill(5101, [{"id": "1"}])
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
        self.window.rows[5101] = [{"kind": "movie", "id": "1", "available": True}]
        self.window.getControl.return_value.getSelectedPosition.return_value = 0
        dialog = Mock()
        with patch.object(self.ui.xbmcgui, "Dialog", return_value=dialog, create=True), \
             patch.object(self.ui, "listitem", return_value="selected-item"):
            self.window.onClick(5101)
        dialog.info.assert_called_once_with("selected-item")
        self.assertFalse(self.window.in_info)


if __name__ == "__main__":
    unittest.main()
