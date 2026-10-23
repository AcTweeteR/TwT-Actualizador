"""Resolve Trakt catalog identities from provider and XStream evidence.

XStream's live premium metadata cache is reusable only when its external ID and
provider year match Trakt; title/year joins alone remain non-actionable.
"""
import hashlib
import json
import math
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from .trakt_provider_index import (catalog_members, catalog_source, external_ids,
                                   read_object, verified_vod_records)
from .trakt_series_index import verified_show_records
from .trakt_live_queue import provider_fingerprint
from .trakt_sync import normalize_ids


def _title_key(value):
    value = re.sub(r"\s*\(\d{4}\)\s*$", "", str(value or ""))
    return "".join(char for char in unicodedata.normalize("NFKD", value).casefold()
                   if char.isalnum())


def _year(value):
    value = str(value or "")
    return value[:4] if re.match(r"^\d{4}", value) else ""


def _scope(root, profile):
    scopes = []
    for stype in ("movie", "series"):
        try:
            source = catalog_source(root / ("data_cache_p%s_xtream_streams_%s.json" %
                                            (profile, stype)))
        except (OSError, ValueError, UnicodeError):
            return ""
        parts = source.split("|")
        if len(parts) < 3:
            return ""
        scope = provider_fingerprint(profile, "Xtream Codes", parts[0], parts[1])
        if not scope:
            return ""
        scopes.append(scope)
        # Redacted catalog copies are useful for offline tests, never for a
        # provider-bound restore decision.
    return scopes[0] if len(scopes) == 2 and scopes[0] == scopes[1] else ""


def _fingerprint(root, profile, kind, provider_id, row, ids, scope):
    catalog = root / ("data_cache_p%s_xtream_streams_%s.json" %
                      (profile, "movie" if kind == "movie" else "series"))
    try:
        stat = catalog.stat()
        generation = [stat.st_size, getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1e9))]
    except OSError:
        generation = []
    value = {"profile": str(profile), "kind": kind, "provider_id": str(provider_id),
             "provider_scope": scope, "title": row.get("title") or row.get("name") or "",
             "year": _year(row.get("year")), "ids": ids, "catalog_generation": generation}
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _provider_time(root, profile, kind, provider_id, row):
    names = ["data_cache_p%s_xtream_streams_%s.json" %
             (profile, "movie" if kind == "movie" else "series")]
    names.append("data_cache_p%s_%s_info_%s.json" %
                 (profile, "vod" if kind == "movie" else "series", provider_id))
    if kind == "show":
        names.append("series_changes_p%s.json" % profile)
    stamps = []
    for name in names:
        try:
            stamps.append((root / name).stat().st_mtime)
        except OSError:
            pass
    if not stamps:
        return ""
    return datetime.fromtimestamp(max(stamps), timezone.utc).isoformat()


def _trakt_aliases(export_payload):
    aliases = {}
    for response in (export_payload or {}).get("responses", []):
        if not isinstance(response, dict) or not isinstance(response.get("data"), list):
            continue
        path = str(response.get("path", ""))
        kind = "movie" if path.endswith("/movies") else "show" if path.endswith("/shows") or path.endswith("/episodes") else ""
        if not kind:
            continue
        field = "movie" if kind == "movie" else "show"
        for item in response["data"]:
            media = item.get(field) if isinstance(item, dict) else None
            if not isinstance(media, dict) or not media.get("title") and not media.get("name"):
                continue
            ids = normalize_ids(media.get("ids"))
            # Trakt identifiers are already normalized under the same names.
            if not ids:
                continue
            key = (kind, tuple(sorted(ids.items())))
            entry = aliases.setdefault(key, {"kind": kind, "ids": ids, "titles": set(), "years": set()})
            entry["titles"].update(str(media[field]) for field in
                                   ("title", "name", "original_title", "original_name")
                                   if media.get(field))
            year = _year(media.get("year"))
            if year:
                entry["years"].add(year)
    return list(aliases.values())


def _source_conflict(root, profile, kind, provider_id, row, premium_paths=()):
    sources = [external_ids(row)]
    details = read_object(root / ("data_cache_p%s_%s_info_%s.json" %
                                  (profile, "vod" if kind == "movie" else "series", provider_id)))
    if details:
        if kind == "movie":
            movie = details.get("movie_data")
            if (isinstance(movie, dict) and str(movie.get("stream_id")) == provider_id
                    and not any(movie.get(key) and row.get(key) and str(movie[key]) != str(row[key])
                                for key in ("name", "year"))):
                sources.append(external_ids(details.get("info")))
        else:
            sources.append(external_ids(details.get("info")))
    if kind == "show":
        state = read_object(root / ("series_changes_p%s.json" % profile)) or {}
        inventory = state.get("episode_inventory", {})
        if isinstance(inventory, dict):
            sources.append(external_ids(inventory.get(provider_id, {})))
    for path in premium_paths:
        cached = read_object(path)
        sources.append(external_ids((cached or {}).get("data")))
    ids = {}
    for source in sources:
        if any(key in ids and ids[key] != value for key, value in source.items()):
            return True
        ids.update(source)
    return False


def _provider_evidence(root, profile, kind, provider_id, row):
    sources = [("provider_catalog", external_ids(row))]
    details = read_object(root / ("data_cache_p%s_%s_info_%s.json" %
                                  (profile, "vod" if kind == "movie" else "series", provider_id)))
    if details:
        if kind == "movie":
            movie = details.get("movie_data")
            if (isinstance(movie, dict) and str(movie.get("stream_id")) == provider_id
                    and not any(movie.get(key) and row.get(key) and str(movie[key]) != str(row[key])
                                for key in ("name", "year"))):
                sources.append(("provider_details", external_ids(details.get("info"))))
        else:
            sources.append(("provider_details", external_ids(details.get("info"))))
    if kind == "show":
        state = read_object(root / ("series_changes_p%s.json" % profile)) or {}
        inventory = state.get("episode_inventory", {})
        if isinstance(inventory, dict):
            sources.append(("series_inventory", external_ids(inventory.get(provider_id, {})))
                           )
    ids, id_evidence = {}, {}
    for source, values in sources:
        for key, value in values.items():
            if key in ids and ids[key] != value:
                return {}, {}, []
            ids[key] = value
            id_evidence.setdefault(key, []).append(source)
    if kind == "movie":
        ids.pop("tvdb", None)
        id_evidence.pop("tvdb", None)
    return ids, id_evidence, [name for name, values in sources if values]


def _premium_cache_entries(root, profile, kind):
    label = "movie" if kind == "movie" else "series"
    entries = {}
    pattern = re.compile(r"data_cache_p%s_premium_meta_%s_([0-9]+)_[^/]+\.json" %
                         (re.escape(str(profile)), label))
    for path in root.glob("data_cache_p%s_premium_meta_%s_*.json" % (profile, label)):
        match = pattern.fullmatch(path.name)
        cached = read_object(path)
        expires = cached.get("expires") if cached else None
        if (not match or not cached or type(expires) not in (int, float)
                or not math.isfinite(expires)):
            continue
        data = cached.get("data")
        if (expires <= time.time() or not isinstance(data, dict)
                or not isinstance(data.get("title"), str) or not data["title"].strip()):
            continue
        ids = external_ids(data)
        if kind == "movie":
            ids.pop("tvdb", None)
        if not ids:
            continue
        entry = entries.setdefault(match.group(1), {"ids": {}, "paths": [], "titles": set()})
        if any(key in entry["ids"] and entry["ids"][key] != value
               for key, value in ids.items()):
            entry["conflict"] = True
        entry["ids"].update(ids)
        entry["paths"].append(path)
        entry["titles"].add(str(data["title"]))
    return entries


def _trakt_cache_match(kind, provider_row, cached, aliases):
    year = _year(provider_row.get("year"))
    title = provider_row.get("title") or provider_row.get("name")
    if not title or not re.fullmatch(r"\d{4}", year):
        return "pending"
    matched = False
    for alias in aliases:
        if alias["kind"] != kind:
            continue
        shared = {key for key, value in cached.items() if alias["ids"].get(key) == value}
        if not shared:
            continue
        matched = True
        if any(key in alias["ids"] and alias["ids"][key] != value
               for key, value in cached.items()):
            return "conflict"
        if alias["years"] != {year}:
            return "conflict"
    return "matched" if matched else "pending"


def _cache_has_trakt_id(kind, cached, aliases):
    return any(alias["kind"] == kind and any(
        alias["ids"].get(key) == value for key, value in cached.items())
        for alias in aliases)


def resolve_identities(directory, *, profile, export_payload=None, include_candidates=False):
    """Return safe verified records plus non-actionable candidates/conflicts.

    No network, file writes, or fuzzy matching. Source cache files are the
    durable evidence; fingerprints make changes detectable after restart.
    """
    if not str(profile).isdigit() or int(profile) < 1:
        raise ValueError("invalid XStream profile")
    root = Path(directory)
    if root.is_symlink():
        raise ValueError("unsafe XStream profile directory")
    scope = _scope(root, profile)
    if not scope:
        return {"verified": [], "candidates": [], "conflicts": [],
                "summary": {"provider_scope_available": False}}

    verified = (verified_vod_records(root, profile=profile) +
                verified_show_records(root, profile=profile))
    aliases = _trakt_aliases(export_payload)
    premium = {"movie": _premium_cache_entries(root, profile, "movie"),
               "show": _premium_cache_entries(root, profile, "show")}
    if include_candidates:
        catalogs = {"movie": catalog_members(root, profile, "movie"),
                    "show": catalog_members(root, profile, "series")}
    else:
        verified_movies = {row['provider_id'] for row in verified if row['kind'] == 'movie'}
        verified_shows = {row['provider_id'] for row in verified if row['kind'] == 'show'}
        cached_movies = {provider_id for provider_id, value in premium["movie"].items()
                         if _cache_has_trakt_id("movie", value["ids"], aliases)}
        cached_shows = {provider_id for provider_id, value in premium["show"].items()
                        if _cache_has_trakt_id("show", value["ids"], aliases)}
        catalogs = {
            "movie": catalog_members(root, profile, "movie", verified_movies | cached_movies)
                     if verified_movies | cached_movies else {},
            "show": catalog_members(root, profile, "series", verified_shows | cached_shows)
                    if verified_shows | cached_shows else {},
        }
    members = {kind: values for kind, values in catalogs.items()}
    enriched = []
    checked_at = datetime.now(timezone.utc).isoformat()
    conflicted = []
    verified_keys = {(item["kind"], item["provider_id"]) for item in verified}
    if include_candidates:
        for kind, items in catalogs.items():
            detail_pattern = "data_cache_p%s_%s_info_*.json" % (profile, "vod" if kind == "movie" else "series")
            detail_ids = {match.group(1) for path in root.glob(detail_pattern)
                          if (match := re.fullmatch(r"data_cache_p[0-9]+_(?:vod|series)_info_([0-9]+)\.json", path.name))}
            for provider_id in (detail_ids | set(premium[kind])) & set(items):
                if ((kind, provider_id) not in verified_keys and
                        _source_conflict(root, profile, kind, provider_id, items[provider_id],
                                         premium[kind].get(provider_id, {}).get("paths", ()))):
                    conflicted.append({"kind": kind, "provider_id": provider_id,
                                       "status": "CONFLICT", "reason": "external_sources_disagree"})
    for record in verified:
        kind, provider_id = record["kind"], record["provider_id"]
        row = members[kind].get(provider_id, {})
        ids, id_evidence, source_labels = _provider_evidence(root, profile, kind, provider_id, row)
        if not ids:
            continue
        enriched.append(dict(record, ids=ids, status="VERIFIED", provenance=source_labels,
                             verification_method="PROVIDER_VERIFIED",
                             id_evidence=id_evidence,
                             provider_scope=scope,
                             verified_at=checked_at,
                             evidence_updated_at=_provider_time(root, profile, kind, provider_id, row),
                             catalog_fingerprint=_fingerprint(root, profile, kind, provider_id,
                                                              row, ids, scope)))

    direct = {(record["kind"], record["provider_id"]): record for record in enriched}
    cache_pending = 0
    conflict_keys_seen = {(item["kind"], item.get("provider_id")) for item in conflicted}
    for kind, entries in premium.items():
        for provider_id, cached in entries.items():
            row = members[kind].get(provider_id)
            if not row:
                continue
            if (kind, provider_id) in conflict_keys_seen:
                continue
            if cached.get("conflict") or _source_conflict(
                    root, profile, kind, provider_id, row, cached["paths"]):
                conflicted.append({"kind": kind, "provider_id": provider_id,
                                   "status": "CONFLICT", "reason": "external_sources_disagree"})
                conflict_keys_seen.add((kind, provider_id))
                existing = direct.pop((kind, provider_id), None)
                if existing:
                    enriched.remove(existing)
                continue
            match = _trakt_cache_match(kind, row, cached["ids"], aliases)
            if match == "conflict":
                conflicted.append({"kind": kind, "provider_id": provider_id,
                                   "status": "CONFLICT", "reason": "trakt_identity_year_or_id_disagrees"})
                conflict_keys_seen.add((kind, provider_id))
                existing = direct.pop((kind, provider_id), None)
                if existing:
                    enriched.remove(existing)
                continue
            if match != "matched":
                cache_pending += 1
                continue
            key = (kind, provider_id)
            existing = direct.get(key)
            ids, id_evidence, provenance = _provider_evidence(root, profile, kind, provider_id, row)
            if any(name in ids and ids[name] != value for name, value in cached["ids"].items()):
                conflicted.append({"kind": kind, "provider_id": provider_id,
                                   "status": "CONFLICT", "reason": "provider_and_xstream_ids_disagree"})
                conflict_keys_seen.add((kind, provider_id))
                if existing:
                    enriched.remove(existing)
                    direct.pop(key, None)
                continue
            ids.update(cached["ids"])
            for name in cached["ids"]:
                id_evidence.setdefault(name, []).append("xstream_premium_cache")
            source_labels = list(dict.fromkeys(provenance + ["xstream_premium_cache"]))
            if existing:
                existing.update(ids=ids, id_evidence=id_evidence, provenance=source_labels,
                                verification_method="PROVIDER_VERIFIED")
                continue
            enriched.append({"profile": str(profile), "kind": kind, "provider_id": provider_id,
                             "ids": ids, "confidence": "verified", "status": "VERIFIED",
                             "verification_method": "XSTREAM_MATCHED",
                             "provenance": source_labels, "id_evidence": id_evidence,
                             "provider_scope": scope, "verified_at": checked_at,
                             "evidence_updated_at": _provider_time(root, profile, kind,
                                                                    provider_id, row),
                             "catalog_fingerprint": _fingerprint(root, profile, kind,
                                                                  provider_id, row, ids, scope)})

    # An external ID linked to multiple provider IDs is not safe to restore.
    owners = {}
    for record in enriched:
        for key, value in record["ids"].items():
            owners.setdefault((record["kind"], key, value), set()).add(record["provider_id"])
    collided = {(kind, provider_id) for record in enriched for kind, provider_id in
                [(record["kind"], record["provider_id"])]
                if any(len(owners[(kind, key, value)]) > 1
                       for key, value in record["ids"].items())}
    conflicts = conflicted + [dict(record, status="CONFLICT", reason="external_id_multiple_provider_items")
                              for record in enriched if (record["kind"], record["provider_id"]) in collided]
    safe = [record for record in enriched
            if (record["kind"], record["provider_id"]) not in collided]

    conflict_keys = {(item["kind"], item["provider_id"]) for item in conflicts}
    verified_ids = {(record["kind"], key, value) for record in safe
                    for key, value in record["ids"].items()}
    title_index = {kind: {} for kind in catalogs}
    for kind, items in catalogs.items() if include_candidates else ():
        for provider_id, row in items.items():
            year = _year(row.get("year"))
            titles = [row.get(field) for field in ("title", "name", "original_title", "original_name")]
            for path in premium[kind].get(provider_id, {}).get("paths", ()):
                cached = read_object(path)
                data = (cached or {}).get("data", {})
                if isinstance(data, dict):
                    titles.extend(data.get(field) for field in
                                  ("title", "name", "original_title", "original_name"))
            for title in titles:
                key = _title_key(title)
                if key:
                    title_index[kind].setdefault(key, []).append((provider_id, year, row))
    verified_keys = {(record["kind"], record["provider_id"]) for record in safe}
    candidates = []
    for alias in aliases:
        if len(alias["years"]) > 1:
            conflicts.append({"kind": alias["kind"], "ids": alias["ids"],
                              "status": "CONFLICT", "reason": "trakt_years_disagree"})
            continue
        if any((alias["kind"], key, value) in verified_ids for key, value in alias["ids"].items()):
            continue
        title_keys = {_title_key(title) for title in alias["titles"] if _title_key(title)}
        candidates_by_id = {}
        for title in title_keys:
            for provider_id, row_year, row in title_index[alias["kind"]].get(title, ()):
                if row_year and alias["years"] and row_year not in alias["years"]:
                    continue
                candidates_by_id[provider_id] = row
        matches = []
        for provider_id, row in candidates_by_id.items():
            key = (alias["kind"], provider_id)
            if key in conflict_keys:
                continue
            if key not in verified_keys and key not in conflict_keys and _source_conflict(
                    root, profile, alias["kind"], provider_id, row,
                    premium[alias["kind"]].get(provider_id, {}).get("paths", ())):
                conflict_keys.add(key)
                conflicted.append({"kind": alias["kind"], "provider_id": provider_id,
                                   "status": "CONFLICT", "reason": "external_sources_disagree"})
                continue
            matches.append(provider_id)
        if matches:
            candidates.append({"kind": alias["kind"], "ids": alias["ids"],
                               "provider_ids": sorted(set(matches), key=lambda x: (len(x), x)),
                               "status": "CANDIDATE", "reason": "normalized_title_year_only"})

    return {"verified": safe, "candidates": candidates, "conflicts": conflicts,
            "summary": {"provider_scope_available": True, "verified_movies": sum(x["kind"] == "movie" for x in safe),
                        "verified_shows": sum(x["kind"] == "show" for x in safe),
                        "provider_verified": sum(x.get("verification_method") == "PROVIDER_VERIFIED" for x in safe),
                        "xstream_matched": sum(x.get("verification_method") == "XSTREAM_MATCHED" for x in safe),
                        "provider_verified_movies": sum(x["kind"] == "movie" and x.get("verification_method") == "PROVIDER_VERIFIED" for x in safe),
                        "provider_verified_shows": sum(x["kind"] == "show" and x.get("verification_method") == "PROVIDER_VERIFIED" for x in safe),
                        "xstream_matched_movies": sum(x["kind"] == "movie" and x.get("verification_method") == "XSTREAM_MATCHED" for x in safe),
                        "xstream_matched_shows": sum(x["kind"] == "show" and x.get("verification_method") == "XSTREAM_MATCHED" for x in safe),
                        "xstream_cache_pending": cache_pending,
                        "xstream_cache_entries": sum(len(entries) for entries in premium.values()),
                        "xstream_cache_missing_provider_item": sum(
                            provider_id not in catalogs[kind]
                            for kind, entries in premium.items() for provider_id in entries),
                        "candidate_links": sum(len(x["provider_ids"]) for x in candidates) if include_candidates else None,
                        "candidate_trakt_items": len(candidates) if include_candidates else None,
                        "candidate_scan": "complete" if include_candidates else "not_requested",
                        "conflicts": len(conflicts),
                        "unverified_movies": (len(catalogs["movie"]) - sum(x["kind"] == "movie" for x in safe)
                                              if include_candidates else None),
                        "unverified_shows": (len(catalogs["show"]) - sum(x["kind"] == "show" for x in safe)
                                             if include_candidates else None)}}
