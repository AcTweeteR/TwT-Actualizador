"""Regressions for simple Testing installer browsing in Kodi."""
from __future__ import annotations

import hashlib
import sys
import unittest
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from build_test_channel import bootstrap_index_html  # noqa: E402


class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.hrefs.extend(value for key, value in attrs if key == "href")


class TestingBootstrapDirectoryTests(unittest.TestCase):
    def test_current_installer_is_the_only_version_listed_at_root(self):
        root = ROOT / "docs/testing/bootstrap"
        latest = "repository.actweeter.testing-1.0.2.zip"
        text = (root / "index.html").read_text(encoding="utf-8")
        self.assertEqual(text, bootstrap_index_html(latest))
        parser = LinkCollector()
        parser.feed(text)
        self.assertEqual(parser.hrefs, [latest, "archive/"])
        self.assertTrue((root / latest).is_file())
        with zipfile.ZipFile(root / latest) as archive:
            self.assertIsNone(archive.testzip())
            addon = ET.fromstring(archive.read("repository.actweeter.testing/addon.xml"))
            self.assertEqual((addon.get("id"), addon.get("version")),
                             ("repository.actweeter.testing", "1.0.2"))

    def test_historical_installer_archive_does_not_break_old_urls(self):
        root = ROOT / "docs/testing/bootstrap"
        older = ["repository.actweeter.testing-1.0.1.zip",
                 "repository.actweeter.testing-1.0.0.zip"]
        parser = LinkCollector()
        parser.feed((root / "archive/index.html").read_text(encoding="utf-8"))
        self.assertEqual(parser.hrefs, older)
        for name in older:
            original, archived = root / name, root / "archive" / name
            self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(),
                             hashlib.sha256(archived.read_bytes()).hexdigest())
            with zipfile.ZipFile(archived) as package:
                self.assertIsNone(package.testzip())

    def test_rejects_unsafe_bootstrap_names(self):
        for filename in ("../repository.actweeter.testing-1.0.2.zip",
                         "repository.actweeter.testing-1.0.2.zip?url=1",
                         "repository.actweeter.testing-1.0.2.zip\"\""):
            with self.assertRaises(ValueError):
                bootstrap_index_html(filename)


if __name__ == "__main__":
    unittest.main()
