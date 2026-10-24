import ast
import os
import sys
import time
import urllib.parse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "addons/service.actweeter/resources/lib"
sys.path.insert(0, str(LIB))

from catalog_refresh import (  # noqa: E402
    SEARCH_REFRESH_TIMEOUT_SECONDS,
    begin_search_operation, finish_search_operation, read_retry_state,
    record_retry_result, recover_search_operations, search_operation,
)
from plugin_query_trace import begin, emit  # noqa: E402
from search_background import (  # noqa: E402
    COORDINATOR_PENDING_CHECK_SECONDS, COORDINATOR_REFRESH_CHECK_SECONDS,
    RefreshGate, plugin_refresh_url, refresh_state_check_due,
    xstream_profile_number,
)


class _Monitor:
    def __init__(self):
        self.checks = 0

    def abortRequested(self):
        self.checks += 1
        return self.checks >= 4

    def waitForAbort(self, _seconds):
        return False


class _Kodi:
    LOGINFO = 1
    LOGWARNING = 2

    def __init__(self, service_profile):
        self.service_profile = service_profile
        self.logs = []
        self.dispatched = []

    def log(self, message, *_args):
        self.logs.append(message)

    def getCondVisibility(self, _condition):
        return True

    def Player(self):
        return None

    def executebuiltin(self, command, _wait=False):
        self.dispatched.append(command)
        url = command[len("RunPlugin("):-1]
        request_id = urllib.parse.parse_qs(
            urllib.parse.urlsplit(url).query)["actweeter_callback"][0]
        finish_search_operation(
            self.service_profile, request_id, "error", now=100001)
        record_retry_result(
            self.service_profile, 1, "error", category="timeout",
            now=100001, jitter=0)


class _Addon:
    def __init__(self, profile):
        self.profile = profile

    def getAddonInfo(self, key):
        return self.profile if key == "profile" else "/addon"

    def getSetting(self, _key):
        return "Profile 1"


class _VFS:
    @staticmethod
    def translatePath(path):
        return path


class _SpotlightRotation:
    @staticmethod
    def tick(*_args, **_kwargs):
        return None


class _TraktScheduler:
    def __init__(self, _path):
        pass

    def dispatch_if_due(self, *_args, **_kwargs):
        return False


class _NullMeasure:
    def __enter__(self):
        return None

    def __exit__(self, *_args):
        return False


def test_failed_refresh_callback_is_terminal_and_backoff_does_not_hide_typeerror(tmp_path):
    service_profile = str(tmp_path / "service")
    xstream_profile = str(tmp_path / "xstream")
    Path(xstream_profile).mkdir()
    service_source = (ROOT / "addons/service.actweeter/service.py").read_text()
    coordinator = next(
        node for node in ast.parse(service_source).body
        if isinstance(node, ast.FunctionDef) and node.name == "_run_coordinator")
    namespace = {
        "RefreshGate": RefreshGate,
        "SpotlightRotation": _SpotlightRotation,
        "_window_id": lambda _kodi: None,
        "time": time,
        "ADDON": _Addon(service_profile),
        "vfs": _VFS(),
        "recover_search_operations": recover_search_operations,
        "TraktSyncScheduler": _TraktScheduler,
        "os": os,
        "trakt_sync_enabled": lambda _path: False,
        "COORDINATOR_REFRESH_CHECK_SECONDS": COORDINATOR_REFRESH_CHECK_SECONDS,
        "COORDINATOR_PENDING_CHECK_SECONDS": COORDINATOR_PENDING_CHECK_SECONDS,
        "refresh_state_check_due": refresh_state_check_due,
        "performance": None,
        "SEARCH_REFRESH_TIMEOUT_SECONDS": SEARCH_REFRESH_TIMEOUT_SECONDS,
        "search_operation": search_operation,
        "emit_plugin_trace": emit,
        "finish_search_operation": finish_search_operation,
        "record_retry_result": record_retry_result,
        "addon_factory": lambda _addon_id: _Addon(xstream_profile),
        "xstream_profile_number": xstream_profile_number,
        "plugin_refresh_url": plugin_refresh_url,
        "begin_plugin_trace": begin,
        "begin_search_operation": begin_search_operation,
        "last_successful_sync": lambda _path, _profile: 1.0,
        "refresh_interval": lambda _path, _profile: 86400,
        "read_retry_state": read_retry_state,
        "_null_measure": _NullMeasure,
    }
    exec(compile(ast.Module(body=[coordinator], type_ignores=[]),
                 "service.py", "exec"), namespace)
    kodi = _Kodi(service_profile)
    now = iter((100000, 100001, 100062))

    namespace["_run_coordinator"](
        kodi, lambda _addon_id: _Addon(xstream_profile), _VFS(),
        clock=lambda: next(now), monitor=_Monitor())

    request_id = urllib.parse.parse_qs(urllib.parse.urlsplit(
        kodi.dispatched[0][len("RunPlugin("):-1]).query)["actweeter_callback"][0]
    assert len(kodi.dispatched) == 1
    assert search_operation(service_profile, request_id)["status"] == "ERROR"
    assert read_retry_state(service_profile, 1)["failures"] == 1
    assert any("state=error" in line for line in kodi.logs)
    assert not any("Search refresh unavailable" in line for line in kodi.logs)
