import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parents[1]


class CandidatePackageBuildTests(unittest.TestCase):
    def test_xstream_zip_contract_rejects_missing_trakt_route(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import build_xstream_package

        class Archive:
            def __init__(self, members):
                self.members = members

            def namelist(self):
                return list(self.members)

            def read(self, name):
                return self.members[name]

        prefix = "plugin.video.xstream-pro/resources/lib/"
        members = {
            prefix + "addon.py": b"".join((
                b'elif mode == "xstream_trakt_sync_consent":',
                b"_tmdb_routes.trakt_sync_consent_route(args)",
                b'elif mode == "xstream_trakt_sync_cycle":',
                b"_tmdb_routes.trakt_sync_cycle_route(args)",
                b'elif mode == "xstream_trakt_sync_once":',
                b"_tmdb_routes.trakt_sync_once_route(args)",)),
            prefix + "tmdb_routes.py": b"".join((
                b"def trakt_sync_consent_route(params):", b"return consent_route(",
                b"def trakt_sync_cycle_route(params):", b"return cycle_route(",
                b"def trakt_sync_once_route(params):", b"return sync_once_route(")),
            prefix + "trakt_auto_routes.py": b"def consent_route( def cycle_route( run_cycle( def sync_once_route( one_shot=True",
            prefix + "trakt_live_consumer.py": b"def apply_batch( verify_batch( write_ack( target == 'tmdb' tmdb_watch_key",
            prefix + "trakt_live_queue.py": b"def verify_batch( def write_ack( target='provider' target not in ('provider', 'tmdb')",
            prefix + "watched_actions.py": b"def tmdb_watch_key( tmdb:movie: tmdb:episode:",
            prefix + "history_store_coordinator.py": b"def install(history):",
            prefix + "history.py": b"_install_history_store_coordinator(__import__(__name__))",
        }
        members[prefix + 'tmdb_routes.py'] += b' trakt.snapshot_request("/users/settings", {}) def _is_watched( tmdb_watch_key'
        for module in ('trakt_sync.py', 'trakt_provider_index.py', 'trakt_series_index.py', 'trakt_episode_index.py'):
            members[prefix + module] = (ROOT / 'addons/service.actweeter/resources/lib' / module).read_bytes()
        members[prefix + 'trakt_snapshot.py'] = (ROOT / 'third_party/xstream/trakt_snapshot.py').read_bytes()
        members[prefix + 'trakt.py'] = b'def snapshot_request( Unsupported snapshot endpoint'
        build_xstream_package.validate_trakt_sync_contract(Archive(members),
                                                            members[prefix + "trakt_live_queue.py"])
        members[prefix + "addon.py"] = members[prefix + "addon.py"].replace(
            b'elif mode == "xstream_trakt_sync_once":', b'elif mode == "missing":')
        with self.assertRaisesRegex(ValueError, "Trakt sync route/dependency incomplete"):
            build_xstream_package.validate_trakt_sync_contract(
                Archive(members), members[prefix + "trakt_live_queue.py"])

    def test_distribution_index_rejects_mixed_trakt_protocol_generation(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import build_distribution_index
        service = ET.Element("addon", id="service.actweeter", version="0.4.75")
        requires = ET.SubElement(service, "requires")
        ET.SubElement(requires, "import", addon="plugin.video.xstream-pro",
                      version="1.1.2.16")
        xstream = ET.Element("addon", id="plugin.video.xstream-pro",
                             version="1.1.2.28~beta14")
        with self.assertRaisesRegex(ValueError, "protocol generation mismatch"):
            build_distribution_index.validate_service_xstream_pair(service, xstream)

    def test_xstream_snapshot_patch_and_sources_are_locked(self):
        manifest = json.loads((ROOT / "third_party/xstream/upstream.json").read_text())
        patch = ROOT / manifest["trakt_snapshot_patch"]
        self.assertEqual(hashlib.sha256(patch.read_bytes()).hexdigest(),
                         manifest["trakt_snapshot_patch_sha256"])
        for name, source in (
                ("trakt_sync.py", ROOT / "addons/service.actweeter/resources/lib/trakt_sync.py"),
                ("trakt_snapshot.py", ROOT / "third_party/xstream/trakt_snapshot.py"),
                ("trakt_live_queue.py", ROOT / "addons/service.actweeter/resources/lib/trakt_live_queue.py"),
                ("trakt_live_consumer.py", ROOT / "third_party/xstream/trakt_live_consumer.py")):
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                             manifest["trakt_snapshot_sources_sha256"][name])
        auto_patch = ROOT / manifest["trakt_auto_cycle_patch"]
        self.assertEqual(hashlib.sha256(auto_patch.read_bytes()).hexdigest(),
                         manifest["trakt_auto_cycle_patch_sha256"])
        auto_routes = ROOT / "third_party/xstream/trakt_auto_routes.py"
        self.assertEqual(hashlib.sha256(auto_routes.read_bytes()).hexdigest(),
                         manifest["trakt_auto_routes_sha256"])
        series_lookup = ROOT / manifest["provider_series_lookup_patch"]
        self.assertEqual(hashlib.sha256(series_lookup.read_bytes()).hexdigest(),
                         manifest["provider_series_lookup_patch_sha256"])
        for filename, key in (("apply_trakt_pkce.py", "trakt_pkce_applier_sha256"),
                               ("trakt_pkce.py", "trakt_pkce_source_sha256")):
            source = ROOT / "third_party/xstream" / filename
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), manifest[key])

    @unittest.skipUnless(os.environ.get("ACTWEETER_XSTREAM_LIVE_ZIP"),
                         "set the exact candidate ZIP to verify provider series navigation")
    def test_packaged_series_lookup_scans_all_items_and_rejects_ambiguous_titles(self):
        package = os.environ["ACTWEETER_XSTREAM_LIVE_ZIP"]
        with zipfile.ZipFile(package) as archive:
            source = archive.read("plugin.video.xstream-pro/resources/lib/addon.py")
        tree = ast.parse(source)
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == "_find_provider_series_id_for_show")
        rows = [{"name": "Other", "series_id": "1"},
                {"name": "The Example", "series_id": "2"},
                {"name": "Last", "series_id": "3"}]
        namespace = {
            "_enabled_profiles_with_credentials": lambda: [(1, "profile")],
            "_get_credentials_for_profile": lambda _: {
                "xtream_url": "https://example.invalid", "xtream_username": "user",
                "xtream_password": "synthetic"},
            "_get_cached_xtream_streams": lambda *_args: rows,
            "_provider_title_key": lambda value: str(value or "").casefold().strip(),
        }
        exec(compile(ast.Module(body=[function], type_ignores=[]), "candidate-addon.py", "exec"),
             namespace)
        result = namespace[function.name]("900", "The Example")
        self.assertEqual(result[3], "2")
        rows.append({"name": "The Example", "series_id": "4"})
        self.assertIsNone(namespace[function.name]("900", "The Example")[0])

    @unittest.skipUnless(os.environ.get("ACTWEETER_XSTREAM_LIVE_ZIP"),
                         "set the exact candidate ZIP to verify stale local catalogs")
    def test_packaged_catalog_routes_serve_stale_local_data_without_remote_refresh(self):
        package = os.environ["ACTWEETER_XSTREAM_LIVE_ZIP"]
        with zipfile.ZipFile(package) as archive:
            source = archive.read("plugin.video.xstream-pro/resources/lib/addon.py")
            catalog_source = archive.read(
                "plugin.video.xstream-pro/resources/lib/catalog_cache.py")
        tree = ast.parse(source)
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in ("_get_cached_xtream_categories",
                                       "_get_cached_xtream_streams")]
        self.assertEqual({node.name for node in functions},
                         {"_get_cached_xtream_categories", "_get_cached_xtream_streams"})
        cached = {"_src": "https://provider|user|password",
                  "_data": [{"id": "local"}]}
        catalog_tree = ast.parse(catalog_source)
        catalog_functions = [node for node in catalog_tree.body
                             if isinstance(node, ast.FunctionDef)
                             and node.name in ("provider_fingerprint", "source_matches")]
        catalog_namespace = {"hashlib": hashlib}
        exec(compile(ast.Module(body=catalog_functions, type_ignores=[]),
                     "candidate-catalog-cache.py", "exec"), catalog_namespace)
        catalog_cache = type("CatalogCache", (), {
            "source_matches": staticmethod(catalog_namespace["source_matches"]),
        })()
        refreshes = []
        namespace = {
            "pm": type("Profiles", (), {"active": 1})(),
            "catalog_cache": catalog_cache,
            "_cache_load": lambda *_args: cached,
            "_cache_valid": lambda *_args, **_kwargs: self.fail(
                "ordinary navigation must not gate local data on its refresh age"),
            "_refresh_catalog_generation": lambda *args, **kwargs: refreshes.append(args),
        }
        exec(compile(ast.Module(body=functions, type_ignores=[]), "candidate-addon.py", "exec"),
             namespace)
        categories = namespace["_get_cached_xtream_categories"](
            "https://provider", "user", "password", "series", profile_num=1)
        streams = namespace["_get_cached_xtream_streams"](
            "https://provider", "user", "password", "series", profile_num=1)
        self.assertEqual(categories, cached["_data"])
        self.assertEqual(streams, cached["_data"])
        self.assertEqual(refreshes, [])

        namespace["_get_cached_xtream_streams"](
            "https://provider", "user", "password", "series", force_refresh=True,
            profile_num=1)
        self.assertEqual(len(refreshes), 1)

    def test_device_code_contract_rejects_legacy_auth_route(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import build_xstream_package

        class Archive:
            def __init__(self, members):
                self.members = members

            def namelist(self):
                return list(self.members)

            def read(self, name):
                return self.members[name]

        prefix = "plugin.video.xstream-pro/resources/lib/"
        members = {
            prefix + "trakt.py": b"def device_code( def poll_device_token(",
            prefix + "tmdb_routes.py": (b"def trakt_authorize_route(params): "
                b"trakt.device_code() trakt.poll_device_token(device_code) "
                b"from lib.trakt_sync_consent import grant provider_scope=scope"),
        }
        build_xstream_package.validate_trakt_device_auth_contract(Archive(members))
        members[prefix + "tmdb_routes.py"] += b" trakt_pkce.begin("
        with self.assertRaisesRegex(ValueError, "legacy Trakt PKCE route"):
            build_xstream_package.validate_trakt_device_auth_contract(Archive(members))

    def test_series_change_package_contract_rejects_stale_or_unscoped_source(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import build_xstream_package

        class Archive:
            def __init__(self, members):
                self.members = members

            def namelist(self):
                return list(self.members)

            def read(self, name):
                return self.members[name]

        prefix = "plugin.video.xstream-pro/resources/lib/"
        members = {
            prefix + "series_changes.py": (
                b"STATE_VERSION=2\nWINDOW_SECONDS=5*86400\n"
                b"def record_catalog(addon, profile_num, items, *, provider=None, complete=True): pass\n"
                b"def record_series_info(addon, profile_num, sid, title, response): pass\n"
                b"def status(addon, profile_num, sid): pass\n"
                b"def recent(addon, profile_num, limit=24): pass\n"),
            prefix + "addon.py": b"provider=(url, user)\nrecord_series_info\n",
            prefix + "premium_routes.py": b"provider=(host, user)\n",
        }
        build_xstream_package.validate_series_changes_contract(Archive(members))
        members[prefix + "series_changes.py"] += b"MAX_EVENTS=50\n"
        with self.assertRaisesRegex(ValueError, "arbitrarily capped"):
            build_xstream_package.validate_series_changes_contract(Archive(members))

    @unittest.skipUnless(os.environ.get("ACTWEETER_XSTREAM_UPSTREAM_ZIP"),
                         "set the pinned upstream ZIP to verify reproducible Device Code build")
    def test_xstream_rebuild_keeps_device_auth_in_exact_candidate_zip(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import build_xstream_package

        with tempfile.TemporaryDirectory() as temp:
            first, second = Path(temp) / "first.zip", Path(temp) / "second.zip"
            source = Path(os.environ["ACTWEETER_XSTREAM_UPSTREAM_ZIP"])
            build_xstream_package.build(source, first)
            build_xstream_package.build(source, second)
            self.assertEqual(hashlib.sha256(first.read_bytes()).hexdigest(),
                             hashlib.sha256(second.read_bytes()).hexdigest())
            with zipfile.ZipFile(first) as archive:
                build_xstream_package.validate_trakt_device_auth_contract(archive)
                self.assertIsNone(archive.testzip())

    def test_service_zip_is_reproducible_and_well_formed(self):
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "service.actweeter-0.4.82.zip"
            subprocess.run([sys.executable, str(ROOT / "tools/build_service_package.py"),
                            "--output", str(package)], check=True,
                           cwd=ROOT, capture_output=True, text=True)
            first_hash = hashlib.sha256(package.read_bytes()).hexdigest()
            second_package = Path(temp) / "service-second.zip"
            subprocess.run([sys.executable, str(ROOT / "tools/build_service_package.py"),
                            "--output", str(second_package)], check=True,
                            cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(hashlib.sha256(second_package.read_bytes()).hexdigest(), first_hash)
            with zipfile.ZipFile(package) as archive:
                self.assertIsNone(archive.testzip())
                addon = ET.fromstring(archive.read("service.actweeter/addon.xml"))
                self.assertEqual(addon.get("version"), "0.4.82")
                self.assertIn("service.actweeter/changelog-0.4.82.txt",
                              archive.namelist())
                for relative in ("resources/lib/addon_update_policy.py",
                                 "resources/lib/trakt_sync.py",
                                 "resources/lib/trakt_projection.py",
                                 "resources/lib/trakt_provider_index.py",
                                 "resources/lib/trakt_restore_ui.py",
                                 "resources/lib/trakt_live_queue.py",
                                 "resources/lib/trakt_auto_cycle.py",
                                 "resources/lib/trakt_sync_consent.py",
                                 "resources/lib/trakt_sync_scheduler.py",
                                 "resources/lib/trakt_identity_resolver.py",
                                 "resources/lib/trakt_restore_importer.py",
                                 "resources/lib/trakt_live_sync.py",
                                 "resources/lib/smart_search_engine.py",
                                 "resources/lib/smart_search_sources.py",
                                 "resources/lib/smart_search_ui.py",
                                 "resources/skins/Default/1080i/AcTweeteRSearch.xml"):
                    self.assertIn("service.actweeter/" + relative, archive.namelist())
                self.assertIn("run_smart_search()", archive.read(
                    "service.actweeter/setup.py").decode())
                self.assertEqual(archive.read(
                    "service.actweeter/resources/lib/smart_search_ui.py"),
                    (ROOT / "addons/service.actweeter/resources/lib/smart_search_ui.py").read_bytes())
                self.assertEqual(archive.read(
                    "service.actweeter/resources/lib/addon_update_policy.py"),
                    (ROOT / "addons/service.actweeter/resources/lib/addon_update_policy.py").read_bytes())
                self.assertEqual(archive.read(
                    "service.actweeter/resources/lib/trakt_sync.py"),
                    (ROOT / "addons/service.actweeter/resources/lib/trakt_sync.py").read_bytes())
                for relative in ("trakt_projection.py", "trakt_provider_index.py",
                                 "trakt_live_queue.py", "trakt_identity_resolver.py",
                                 "trakt_restore_ui.py", "diagnostic_plugin.py"):
                    self.assertEqual(archive.read("service.actweeter/resources/lib/" + relative),
                                     (ROOT / "addons/service.actweeter/resources/lib" / relative).read_bytes())
                layout_tree = ast.parse(archive.read(
                    'service.actweeter/resources/lib/interface_layout.py'))
                retries = next(node.value.args[0] for node in layout_tree.body
                               if isinstance(node, ast.Assign)
                               and any(isinstance(target, ast.Name)
                                       and target.id == 'RETRYABLE_INTERFACE_RESULTS'
                                       for target in node.targets))
                self.assertNotIn('GENERATED_XML_PROPERTY_MISSING', ast.literal_eval(retries))
                self.assertIn('_matches_profile', archive.read(
                    'service.actweeter/resources/lib/interface_layout.py').decode())
                self.assertIn('_offer_automatic_previews', archive.read(
                    'service.actweeter/setup.py').decode())
                self.assertFalse(any(name.endswith((".pyc", ".pyo"))
                                     or "__pycache__" in name.split("/")
                                     for name in archive.namelist()))
                for name in archive.namelist():
                    if name.endswith(".py"):
                        ast.parse(archive.read(name), filename=name)

    def test_candidate_distribution_index_is_testing_only(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import build_distribution_index

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            service = output / "service.actweeter-0.4.82.zip"
            subprocess.run([sys.executable, str(ROOT / "tools/build_service_package.py"),
                            "--output", str(service)], check=True,
                           cwd=ROOT, capture_output=True, text=True)
            skin = output / "skin.actweeter-1.2.32~beta8.zip"
            subprocess.run([sys.executable, str(ROOT / "tools/build_skin_package.py"),
                            "--output", str(skin)], check=True,
                           cwd=ROOT, capture_output=True, text=True)
            with zipfile.ZipFile(skin) as archive:
                self.assertIn(b"RunScript(service.actweeter,smart_search)", archive.read(
                    "skin.actweeter/1080i/Custom_1109_BingieSearch.xml"))
                for filename in ("Includes.xml", "IncludesBingie.xml", "IncludesBackgroundBuilding.xml"):
                    self.assertEqual(archive.read("skin.actweeter/1080i/" + filename),
                                     (ROOT / "addons/skin.actweeter/1080i" / filename).read_bytes())
            xstream = output / "plugin.video.xstream-pro-1.1.2.28~beta20.zip"
            self._write_addon_fixture(xstream, "plugin.video.xstream-pro", "1.1.2.28~beta20")
            rivulet_repository = ROOT / "third_party/rivulet/repository.rivulet-1.0.2.zip"
            index_path, md5_path = build_distribution_index.build(
                REPOSITORY_ROOT / "docs/testing/repo/repository.actweeter.testing/repository.actweeter.testing-1.0.2.zip",
                skin,
                service,
                xstream,
                output / "index",
                rivulet_repository)
            payload = index_path.read_bytes()
            versions = {node.get("id"): node.get("version")
                        for node in ET.fromstring(payload).findall("addon")}
            self.assertEqual(versions, {
                "repository.actweeter.testing": "1.0.2",
                "service.actweeter": "0.4.82",
                "skin.actweeter": "1.2.32~beta8",
                "plugin.video.xstream-pro": "1.1.2.28~beta20",
                "repository.rivulet": "1.0.2",
            })
            self.assertEqual(hashlib.md5(payload).hexdigest(),
                             md5_path.read_text(encoding="ascii").strip())

            channel = output / "channel"
            subprocess.run([
                sys.executable, str(REPOSITORY_ROOT / "tools/build_test_channel.py"),
                "--repository-source", str(REPOSITORY_ROOT / "testing/repository.actweeter.testing"),
                "--service-zip", str(service), "--skin-zip", str(skin),
                "--xstream-zip", str(xstream), "--output", str(channel),
            ], check=True, cwd=REPOSITORY_ROOT, capture_output=True, text=True)
            self.assertEqual((channel / "repo/addons.xml").read_bytes(), payload)
            self.assertEqual((channel / "repo/addons.xml.md5").read_text().strip(),
                             md5_path.read_text().strip())
            self.assertEqual((channel / "repo/service.actweeter/changelog-0.4.82.txt").read_bytes(),
                             (ROOT / "addons/service.actweeter/changelog-0.4.82.txt").read_bytes())
            self.assertEqual((channel / "repo/skin.actweeter/changelog-1.2.32~beta8.txt").read_bytes(),
                             (ROOT / "addons/skin.actweeter/changelog-1.2.32~beta8.txt").read_bytes())

    @staticmethod
    def _write_addon_fixture(path, addon_id, version):
        root = ET.Element("addon", id=addon_id, version=version)
        ET.SubElement(root, "extension", point="xbmc.addon.metadata")
        payload = ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(addon_id + "/addon.xml", payload)


if __name__ == "__main__":
    unittest.main()
