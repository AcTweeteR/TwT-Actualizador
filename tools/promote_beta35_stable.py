#!/usr/bin/env python3
"""Create-only Stable promotion of the verified Beta35 Testing packages."""
import argparse
import json
import tempfile
from pathlib import Path

import promote_beta34_stable as promotion


VERSIONS = {
    "skin.actweeter": ("1.2.36~beta5", "1.2.37"),
    "service.actweeter": ("0.4.94~beta9", "0.4.95"),
    "plugin.video.xstream-pro": ("1.1.2.36~beta4", "1.1.2.37"),
}
NOTES = {
    "skin.actweeter": b"1.2.37 Stable - verified Beta35 Trakt recommendations.\n",
    "service.actweeter": b"0.4.95 Stable - verified Beta35 Trakt recommendations and required add-ons.\n",
}


def build(output: Path) -> dict:
    root = promotion.ROOT
    previous = "7c5f5f24f0bf73ebcf800251c1183c703151c8ee3025f3efc8a61bc0b9b96589"
    archived_index = root / "manifests/archive/beta34-stable-addons.xml"
    if promotion.sha(archived_index.read_bytes()) != previous:
        raise ValueError("previous Stable index differs from the verified release")
    return promotion.build(
        output,
        beta_manifest=root / "manifests/actweeter-beta35-20261027.json",
        versions=VERSIONS,
        testing_index_path=root / "manifests/archive/beta35-testing-addons.xml",
        stable_index_path=archived_index,
        notes=NOTES,
        previous_index_sha256=previous,
        release="actweeter-stable-beta35-20261027",
        beta_release="actweeter-beta35-20261027",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    output = parser.parse_args().output_dir.expanduser().resolve()
    if output.exists() or output.is_symlink():
        raise ValueError("refusing to overwrite Stable candidate")
    with tempfile.TemporaryDirectory(prefix=".actweeter-promotion-", dir=output.parent) as tmp:
        stage = Path(tmp) / "candidate"
        manifest = build(stage)
        current = promotion.sha((promotion.ROOT / "repo/addons.xml").read_bytes())
        if current not in (manifest["previous_index_sha256"], manifest["index_sha256"]):
            raise ValueError("current Stable index is neither predecessor nor this promotion")
        stage.rename(output)
    print(json.dumps({"output": str(output), "index_sha256": manifest["index_sha256"]}))


if __name__ == "__main__":
    main()
