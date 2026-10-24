import ast
import os
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "addons/service.actweeter/setup.py"
SERVICE = ROOT / "addons/service.actweeter/service.py"


def _functions(path, names, namespace):
    tree = ast.parse(path.read_bytes(), filename=str(path))
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name in names]
    return exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"),
                namespace)


class StartupIntroTests(unittest.TestCase):
    def setUp(self):
        self.builtins = []
        self.properties = {}
        self.mode = "actweeter_video"
        self.has_media = False
        self.has_video = False
        self.claimed = False
        self.claim_available = True
        self.kodi = SimpleNamespace(
            LOGINFO=1, LOGWARNING=2,
            getInfoLabel=lambda key: self.mode if key == "Skin.String(splash_screen)"
            else ("1" if "AcTweeteRIntroPlayback)" in key
                  and self.properties.get("AcTweeteRIntroPlayback") else ""),
            getCondVisibility=lambda condition: self.has_media if condition == "Player.HasMedia"
            else self.has_video,
            executebuiltin=lambda command, *_: self.builtins.append(command),
            log=lambda *_: None,
        )
        window = SimpleNamespace(
            setProperty=lambda key, value: self.properties.__setitem__(key, value),
            getProperty=lambda key: self.properties.get(key, ""),
        )
        self.globals = {
            "xbmc": self.kodi,
            "xbmcgui": SimpleNamespace(Window=lambda _window: window),
            "os": os,
            "_intro_session_path": lambda: "/profile/intro_session.json",
            "claim_process_session": self._claim,
        }
        _functions(SETUP, {"_play_intro", "_intro_watchdog"}, self.globals)

    def _claim(self, *_):
        if not self.claimed or not self.claim_available:
            return False
        self.claim_available = False
        return True

    def test_intro_starts_once_and_not_over_an_existing_player(self):
        self.claimed = True
        self.globals["_play_intro"]()
        self.assertIn("ActivateWindow(1103)", self.builtins)
        self.assertIn("SetProperty(AcTweeteRIntroPlayback,1,Home)", self.builtins)
        self.assertEqual(self.properties["AcTweeteRStartupIntroActive"], "1")
        self.builtins.clear()
        self.globals["_play_intro"]()
        self.assertEqual(self.builtins, [])

        self.builtins.clear()
        self.claimed = True
        self.claim_available = True
        self.has_media = True
        self.globals["_play_intro"]()
        self.assertEqual(self.builtins, [])

    def test_missing_intro_watchdog_recovers_but_never_stops_valid_video(self):
        self.properties["AcTweeteRIntroPlayback"] = "1"
        self.has_video = True
        self.globals["_intro_watchdog"]()
        self.assertEqual(self.builtins, [])
        self.has_video = False
        self.globals["_intro_watchdog"]()
        self.assertEqual(self.builtins, [
            "ClearProperty(AcTweeteRIntroPlayback,Home)",
            "ClearProperty(StartupMask,Home)",
            "Dialog.Close(1103,true)",
        ])

    def test_intro_terminal_event_releases_only_its_startup_mask(self):
        tree = ast.parse(SERVICE.read_bytes(), filename=str(SERVICE))
        player = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                      and node.name == "SlyGuyTrailerReturnPlayer")
        method = next(node for node in player.body if isinstance(node, ast.FunctionDef)
                      and node.name == "_finish_intro")
        namespace = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(SERVICE), "exec"),
             namespace)

        class Player:
            intro_playback_active = True
            kodi = self.kodi

        Player._finish_intro = namespace["_finish_intro"]
        instance = Player()
        self.assertTrue(instance._finish_intro("ended"))
        self.assertFalse(instance.intro_playback_active)
        self.assertEqual(self.builtins[-3:], [
            "ClearProperty(AcTweeteRIntroPlayback,Home)",
            "ClearProperty(StartupMask,Home)",
            "Dialog.Close(1103,true)",
        ])


if __name__ == "__main__":
    unittest.main()
