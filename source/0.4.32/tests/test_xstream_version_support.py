import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addons/service.actweeter/resources"))
from lib.xstream_setup import (  # noqa: E402
    inspect_xstream_compatibility,
    parse_xstream_version,
    xstream_version_satisfies,
)


def _compatible_addon(root, version):
    (root / "resources/lib").mkdir(parents=True)
    ET.ElementTree(ET.fromstring(
        '<addon id="plugin.video.xstream-pro" version="%s">'
        '<requires><import addon="xbmc.python" version="3.0.1"/>'
        '<import addon="script.module.requests" version="2.22.0"/>'
        '<import addon="pvr.iptvsimple" version="21.4.0"/></requires></addon>'
        % version)).write(root / "addon.xml")
    settings = ET.Element("settings")
    for key, (kind, _default) in __import__("lib.xstream_setup", fromlist=["PROFILE_SETTINGS"]).PROFILE_SETTINGS.items():
        ET.SubElement(settings, "setting", id=key, type=kind)
    ET.ElementTree(settings).write(root / "resources/settings.xml")
    (root / "resources/lib/addon.py").write_text(
        'if mode == "actweeter_refresh_profile": pass\n'
        'callback = args.get("actweeter_callback", [""])[0]\n'
        'route = "catalog_refresh_result"\n', encoding="utf-8")
    (root / "resources/lib/premium_routes.py").write_text(
        "def catalog(): pass\ndef metadata(): pass\ndef dispatch(): pass\n",
        encoding="utf-8")
    (root / "resources/lib/series_changes.py").write_text(
        "def record_catalog(): pass\ndef record_series_info(): pass\ndef status(): pass\n",
        encoding="utf-8")


class XStreamVersionSupportTests(unittest.TestCase):
  def test_future_versions_use_numeric_prerelease_order_not_a_closed_list(self):
    self.assertTrue(xstream_version_satisfies("1.1.2.100~beta1"))
    self.assertTrue(xstream_version_satisfies("1.1.3.0"))
    self.assertGreater(parse_xstream_version("1.1.2.10"), parse_xstream_version("1.1.2.9"))
    self.assertLess(parse_xstream_version("1.1.2.28~beta8"), parse_xstream_version("1.1.2.28"))
    self.assertGreater(parse_xstream_version("1.1.2.28~beta10"), parse_xstream_version("1.1.2.28~beta9"))
    self.assertFalse(xstream_version_satisfies("1.1.1.99"))
    self.assertIsNone(parse_xstream_version("1.1.2.28~preview1"))


  def test_new_beta_and_stable_are_accepted_when_the_actual_contract_is_present(self):
    for version in ("1.1.2.100~beta1", "1.1.3.0"):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _compatible_addon(root, version)
            self.assertEqual(inspect_xstream_compatibility(root, version), (True, ()))


  def test_capability_failure_reports_the_missing_integration_not_a_version_failure(self):
    version = "1.1.2.99~beta1"
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        _compatible_addon(root, version)
        (root / "resources/lib/addon.py").write_text(
            'if mode == "search": pass\n', encoding="utf-8")
        compatible, missing = inspect_xstream_compatibility(root, version)
        self.assertFalse(compatible)
        self.assertIn("profile_refresh_route", missing)
        self.assertIn("catalog_refresh_callback", missing)
        self.assertNotIn("version>=1.1.2", missing)


  def test_manifest_version_and_profile_schema_are_part_of_the_contract(self):
    version = "1.1.2.50"
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        _compatible_addon(root, version)
        settings = ET.parse(root / "resources/settings.xml")
        settings.find(".//setting[@id='profile_1_xtream_password']").set("type", "bool")
        settings.write(root / "resources/settings.xml")
        compatible, missing = inspect_xstream_compatibility(root, "1.1.2.51")
        self.assertFalse(compatible)
        self.assertIn("addon_manifest_identity", missing)
        self.assertIn("xtream_profile_settings", missing)

  def test_dependency_versions_are_part_of_the_contract(self):
    version = "1.1.2.50~beta1"
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        _compatible_addon(root, version)
        manifest = ET.parse(root / "addon.xml")
        manifest.find("./requires/import[@addon='script.module.requests']").set(
            "version", "2.21.9")
        manifest.write(root / "addon.xml")
        compatible, missing = inspect_xstream_compatibility(root, version)
        self.assertFalse(compatible)
        self.assertIn("required_dependencies", missing)

  @unittest.skipUnless(os.environ.get("ACTWEETER_XSTREAM_LIVE_ZIP"),
                       "set the exact candidate ZIP for packaged capability validation")
  def test_exact_candidate_zip_satisfies_the_installer_contract(self):
    package = os.environ["ACTWEETER_XSTREAM_LIVE_ZIP"]
    with tempfile.TemporaryDirectory() as temp, zipfile.ZipFile(package) as archive:
        prefix = "plugin.video.xstream-pro/"
        for member in ("addon.xml", "resources/settings.xml",
                       "resources/lib/addon.py", "resources/lib/premium_routes.py",
                       "resources/lib/series_changes.py"):
            target = Path(temp) / member
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(prefix + member))
        version = ET.parse(Path(temp) / "addon.xml").getroot().get("version")
        self.assertEqual(inspect_xstream_compatibility(temp, version), (True, ()))
