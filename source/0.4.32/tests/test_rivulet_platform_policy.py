"""Only embedded Rivulet management is incompatible with Apple TV."""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/service.actweeter/resources/lib"))
import platform_support as policy

class RivuletPlatformPolicyTests(unittest.TestCase):
    def test_appletv_model_wins_over_darwin_osx_condition(self):
        with patch.object(policy.platform, "machine", return_value="AppleTV11,1"):
            self.assertEqual(policy.detect_platform(lambda key: key == "System.Platform.OSX"), "tvos")

    def test_tvos_changes_only_embedded_switch_once(self):
        addon = Mock()
        addon.getSetting.return_value = "true"
        factory = Mock(return_value=addon)
        with patch.object(policy, "detect_platform", return_value="tvos"):
            self.assertEqual(policy.configure_rivulet(lambda _: True, factory), "external_only")
            addon.setSetting.assert_called_once_with("server_enable", "false")
            addon.getSetting.return_value = "false"
            self.assertEqual(policy.configure_rivulet(lambda _: True, factory), "already_external_only")
            addon.setSetting.assert_called_once()
        factory.assert_called_with("plugin.video.rivulet")

    def test_supported_platform_never_reads_or_writes_rivulet(self):
        for platform_name in ("macos", "android", "unknown"):
            factory = Mock()
            with patch.object(policy, "detect_platform", return_value=platform_name):
                self.assertEqual(policy.configure_rivulet(lambda _: False, factory), "unchanged")
            factory.assert_not_called()

    def test_missing_addon_is_not_installed(self):
        factory = Mock(side_effect=RuntimeError("missing"))
        with patch.object(policy, "detect_platform", return_value="tvos"):
            self.assertEqual(policy.configure_rivulet(lambda _: True, factory), "not_installed")

if __name__ == "__main__":
    unittest.main()
