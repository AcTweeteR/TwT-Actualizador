import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("feed_audit", ROOT / "tools/audit_installer_dependencies.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class FeedAuditTests(unittest.TestCase):
    def test_minimum_versions_optional_imports_and_missing_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            feed = Path(directory) / "index.xml"
            feed.write_text('<addons><addon id="root" version="2.0.0"><requires>'
                            '<import addon="mandatory" version="3.0.0"/>'
                            '<import addon="optional" optional="true"/>'
                            '</requires></addon><addon id="mandatory" version="2.0.0"/></addons>')
            with patch.object(audit, "all_addons", return_value={"root": {"minimum": "1.0.0", "required": True}}):
                result = audit.audit([("fixture", feed)])
            rows = {row["id"]: row for row in result["dependencies"]}
            self.assertEqual(rows["root"]["status"], "AVAILABLE_METADATA")
            self.assertEqual(rows["mandatory"]["status"], "NOT_IN_FETCHED_FEEDS")
            self.assertTrue(rows["mandatory"]["required"])
            self.assertFalse(rows["optional"]["required"])
            self.assertEqual(result["runtime"], "NOT_TESTED")
