"""Read-only, secret-minimizing Kodi diagnostics for AcTweeteR.

The report is transported as bounded Kodi plugin-directory labels so a
trusted LAN client can retrieve it through the existing authenticated Kodi
JSON-RPC service. No listener, file source, or external upload is required.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse

REPORT_PREFIX = "ACTWEETER-DIAG-V1"
CHUNK_SIZE = 1500
MAX_REPORT_BYTES = 256 * 1024
MAX_LOG_LINES = 80
MAX_LOG_TAIL_BYTES = 1024 * 1024

_RELEVANT_LOG = re.compile(
    r"(?:pvr|iptv|xstream|actweeter|addon|dependency|failed|error|warning|initializ)",
    re.IGNORECASE,
)
_URL = re.compile(r"(?i)\b(?:https?|rtmp|plugin|smb|nfs)://[^\s<>\"']+")
_AUTH = re.compile(
    r"(?i)(authorization|cookie|password|passwd|username|user|token|secret|"
    r"api[_-]?key|client[_-]?secret)(\s*[:=]\s*)([^\s,;]+)"
)
_AUTH_HEADER = re.compile(r"(?im)(authorization|cookie)(\s*[:=]\s*)[^\r\n]+")
_JSON_AUTH = re.compile(
    r"(?i)([\"']?(?:password|passwd|username|user|token|secret|api[_-]?key|"
    r"client[_-]?secret)[\"']?\s*[:=]\s*[\"']?)([^\"'\s,;}&]+)"
)
_PATH = re.compile(
    r"(?:(?:special|file)://[^\s,;]+|"
    r"/(?:Users|private/var|var/mobile|storage/emulated|data/user)/[^\s,;]+|"
    r"[A-Za-z]:\\Users\\[^\s,;]+)"
)
_HOST = re.compile(r"(?i)\b(?:[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}|(?:\d{1,3}\.){3}\d{1,3})(?::\d{1,5})?\b")


def sanitize_log_line(line):
    """Keep useful error text while removing URLs, secrets and personal paths."""
    value = str(line).replace("\x00", "")
    value = _URL.sub("<URL_REDACTED>", value)
    value = _AUTH_HEADER.sub(lambda match: match.group(1) + match.group(2) + "<REDACTED>", value)
    value = _JSON_AUTH.sub(lambda match: match.group(1) + "<REDACTED>", value)
    value = _AUTH.sub(lambda match: match.group(1) + match.group(2) + "<REDACTED>", value)
    value = _PATH.sub("<PATH_REDACTED>", value)
    value = _HOST.sub("<HOST_REDACTED>", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:1000]


def relevant_log_lines(text, *, limit=MAX_LOG_LINES):
    """Return only matching, redacted lines from a bounded Kodi log tail."""
    selected = []
    for line in str(text or "").splitlines()[-max(1, limit * 4):]:
        if _RELEVANT_LOG.search(line):
            cleaned = sanitize_log_line(line)
            if cleaned:
                selected.append(cleaned)
    return selected[-max(1, min(int(limit), MAX_LOG_LINES)):]


def addon_snapshot(addons):
    """Allowlist installed add-on metadata; discard paths and free-form errors."""
    result = []
    for addon in addons if isinstance(addons, list) else []:
        if not isinstance(addon, dict):
            continue
        addon_id = addon.get("addonid")
        version = addon.get("version")
        if not isinstance(addon_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,160}", addon_id):
            continue
        dependencies = []
        raw_dependencies = addon.get("xml_dependencies") or addon.get("dependencies", [])
        for dependency in raw_dependencies:
            if not isinstance(dependency, dict):
                continue
            dep_id = dependency.get("addonid")
            dep_version = dependency.get("version")
            if isinstance(dep_id, str) and re.fullmatch(r"[A-Za-z0-9._-]{1,160}", dep_id):
                dependencies.append({
                    "addonid": dep_id,
                    "version": dep_version if isinstance(dep_version, str) else "",
                    "optional": dependency.get("optional") is True,
                })
        source = addon.get("source", "")
        result.append({
            "addonid": addon_id,
            "version": version if isinstance(version, str) else "",
            "enabled": addon.get("enabled") is True,
            "broken": bool(addon.get("broken")),
            "source": source if isinstance(source, str) and
            re.fullmatch(r"(?:repository\.[A-Za-z0-9._-]+)?", source) else "unknown",
            "license": str(addon.get("license", ""))[:160],
            "platform": str(addon.get("platform", "unknown"))[:80],
            "provider": str(addon.get("provider", ""))[:120],
            "dependencies": sorted(dependencies, key=lambda entry: entry["addonid"]),
        })
    return sorted(result, key=lambda entry: entry["addonid"])


def report_payload(*, kodi_version, platform, addons, xstream_profiles,
                   pvr_methods, log_text, captured_at):
    """Build a stable report from already-sanitized scalar inputs."""
    profiles = []
    for profile in xstream_profiles if isinstance(xstream_profiles, list) else []:
        if not isinstance(profile, dict):
            continue
        number = profile.get("profile")
        if type(number) is int and 1 <= number <= 10:
            profiles.append({
                "profile": number,
                "enabled": profile.get("enabled") is True,
                "endpoint_present": profile.get("endpoint_present") is True,
                "username_present": profile.get("username_present") is True,
                "password_present": profile.get("password_present") is True,
            })
    pvr = {}
    for method, result in (pvr_methods or {}).items():
        if not isinstance(method, str) or not re.fullmatch(r"PVR\.[A-Za-z]+", method):
            continue
        if isinstance(result, dict) and "error" in result:
            code = result.get("error", {}).get("code") if isinstance(result.get("error"), dict) else None
            pvr[method] = {"error_code": code if type(code) is int else None}
        elif isinstance(result, dict):
            allowed = {"available", "scanning", "client_count", "channel_group_count"}
            pvr[method] = {key: value for key, value in result.items()
                           if key in allowed and type(value) in (bool, int)}
            pvr[method]["ok"] = True
        else:
            pvr[method] = {"ok": False}
    return {
        "schema": 1,
        "captured_at": str(captured_at)[:40],
        "kodi_version": str(kodi_version)[:80],
        "platform": str(platform)[:24],
        "addons": addon_snapshot(addons),
        "xstream_profiles": sorted(profiles, key=lambda entry: entry["profile"]),
        "pvr": pvr,
        "log": {"sanitized": True, "lines": relevant_log_lines(log_text)},
    }


def encode_report_chunks(report, *, chunk_size=CHUNK_SIZE):
    """Return labels carrying a digest-protected UTF-8 report, in bounded parts."""
    raw = json.dumps(report, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    if len(raw) > MAX_REPORT_BYTES:
        raise ValueError("diagnostic report exceeds size limit")
    if type(chunk_size) is not int or not 128 <= chunk_size <= 6000:
        raise ValueError("invalid diagnostic chunk size")
    encoded = urllib.parse.quote_from_bytes(raw, safe="")
    # Percent encoding is deterministic ASCII and safe in Kodi labels.
    digest = hashlib.sha256(raw).hexdigest()
    chunks = [encoded[i:i + chunk_size] for i in range(0, len(encoded), chunk_size)] or [""]
    total = len(chunks)
    return ["%s:%s:%d/%d:%s" % (REPORT_PREFIX, digest, index, total, chunk)
            for index, chunk in enumerate(chunks, 1)]


def decode_report_labels(labels):
    """Validate and decode labels returned by Kodi Files.GetDirectory."""
    if not isinstance(labels, list) or not labels:
        raise ValueError("diagnostic response is empty")
    parsed = {}
    expected_hash = expected_total = None
    for label in labels:
        if not isinstance(label, str):
            raise ValueError("invalid diagnostic label")
        match = re.fullmatch(
            re.escape(REPORT_PREFIX) + r":([0-9a-f]{64}):([1-9][0-9]*)/([1-9][0-9]*):(.*)",
            label,
        )
        if not match:
            raise ValueError("unexpected diagnostic label format")
        digest, index_text, total_text, chunk = match.groups()
        index, total = int(index_text), int(total_text)
        if total > 1000 or index > total or (expected_hash and digest != expected_hash):
            raise ValueError("invalid diagnostic sequence")
        if expected_total is not None and total != expected_total:
            raise ValueError("inconsistent diagnostic sequence")
        expected_hash, expected_total = digest, total
        if index in parsed:
            raise ValueError("duplicate diagnostic chunk")
        parsed[index] = chunk
    if len(parsed) != expected_total or sorted(parsed) != list(range(1, expected_total + 1)):
        raise ValueError("incomplete diagnostic sequence")
    raw = urllib.parse.unquote_to_bytes("".join(parsed[index] for index in range(1, expected_total + 1)))
    if len(raw) > MAX_REPORT_BYTES or hashlib.sha256(raw).hexdigest() != expected_hash:
        raise ValueError("diagnostic checksum mismatch")
    report = json.loads(raw.decode("utf-8"))
    if not isinstance(report, dict) or report.get("schema") != 1:
        raise ValueError("unsupported diagnostic schema")
    return report
