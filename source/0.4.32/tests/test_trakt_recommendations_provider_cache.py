"""Contract checks for the shared provider match cache in the built candidate."""
import ast
import os
import zipfile
from pathlib import Path


def test_recommendation_cache_reuses_identity_and_invalidates_on_new_catalog():
    with zipfile.ZipFile(os.environ["ACTWEETER_XSTREAM_LIVE_ZIP"]) as archive:
        source = archive.read("plugin.video.xstream-pro/resources/lib/addon.py").decode("utf-8")
    tree = ast.parse(source)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_provider_match_cached")
    code = compile(ast.Module(body=[function], type_ignores=[]), "<provider-match>", "exec")
    calls = []
    namespace = {"_PROVIDER_MATCH_MEMO": {"cache": None, "matches": {}},
                 "_provider_year": lambda *args: next((str(x) for x in args if x), ""),
                 "_provider_title_key": lambda value: str(value).lower(),
                 "_provider_availability_item_available": lambda item, cache, strict_title_year=False: calls.append((id(cache), strict_title_year)) or bool(cache["available"])}
    exec(code, namespace)
    match = namespace["_provider_match_cached"]
    item = {"tmdb_type": "movie", "title": "Test", "year": 2026}
    first = {"available": True}
    assert match(item, first, True) is True
    assert match(item, first, True) is True
    assert len(calls) == 1
    second = {"available": False}
    assert match(item, second, True) is False
    assert len(calls) == 2
    assert match(item, second, False) is False
    assert len(calls) == 3
    assert len(namespace["_PROVIDER_MATCH_MEMO"]["matches"]) == 2
