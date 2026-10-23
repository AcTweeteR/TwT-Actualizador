import ast
import hashlib
import json
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
            prefix + "trakt_live_consumer.py": b"def apply_batch( verify_batch( write_ack(",
            prefix + "trakt_live_queue.py": b"def verify_batch( def write_ack(",
            prefix + "history_store_coordinator.py": b"def install(history):",
            prefix + "history.py": b"_install_history_store_coordinator(__import__(__name__))",
        }
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
        service = ET.Element("addon", id="service.actweeter", version="0.4.58")
        requires = ET.SubElement(service, "requires")
        ET.SubElement(requires, "import", addon="plugin.video.xstream-pro",
                      version="1.1.2.16")
        xstream = ET.Element("addon", id="plugin.video.xstream-pro",
                             version="1.1.2.27~beta1")
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

    def test_service_zip_is_reproducible_and_well_formed(self):
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "service.actweeter-0.4.58.zip"
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
                self.assertEqual(addon.get("version"), "0.4.58")
                self.assertIn("service.actweeter/changelog-0.4.58.txt",
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
                                 "trakt_live_queue.py",
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
            service = output / "service.actweeter-0.4.58.zip"
            subprocess.run([sys.executable, str(ROOT / "tools/build_service_package.py"),
                            "--output", str(service)], check=True,
                           cwd=ROOT, capture_output=True, text=True)
            skin = output / "skin.actweeter-1.2.32~beta1.zip"
            subprocess.run([sys.executable, str(ROOT / "tools/build_skin_package.py"),
                            "--output", str(skin)], check=True,
                           cwd=ROOT, capture_output=True, text=True)
            with zipfile.ZipFile(skin) as archive:
                self.assertIn(b"RunScript(service.actweeter,smart_search)", archive.read(
                    "skin.actweeter/1080i/Custom_1109_BingieSearch.xml"))
                for filename in ("Includes.xml", "IncludesBingie.xml", "IncludesBackgroundBuilding.xml"):
                    self.assertEqual(archive.read("skin.actweeter/1080i/" + filename),
                                     (ROOT / "addons/skin.actweeter/1080i" / filename).read_bytes())
            xstream = output / "plugin.video.xstream-pro-1.1.2.27~beta1.zip"
            self._write_addon_fixture(xstream, "plugin.video.xstream-pro", "1.1.2.27~beta1")
            index_path, md5_path = build_distribution_index.build(
                REPOSITORY_ROOT / "docs/testing/repo/repository.actweeter.testing/repository.actweeter.testing-1.0.2.zip",
                skin,
                service,
                xstream,
                output / "index")
            payload = index_path.read_bytes()
            versions = {node.get("id"): node.get("version")
                        for node in ET.fromstring(payload).findall("addon")}
            self.assertEqual(versions, {
                "repository.actweeter.testing": "1.0.2",
                "service.actweeter": "0.4.58",
                "skin.actweeter": "1.2.32~beta1",
                "plugin.video.xstream-pro": "1.1.2.27~beta1",
            })
            self.assertEqual(hashlib.md5(payload).hexdigest(),
                             md5_path.read_text(encoding="ascii").strip())

    @staticmethod
    def _write_addon_fixture(path, addon_id, version):
        root = ET.Element("addon", id=addon_id, version=version)
        ET.SubElement(root, "extension", point="xbmc.addon.metadata")
        payload = ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(addon_id + "/addon.xml", payload)


if __name__ == "__main__":
    unittest.main()
