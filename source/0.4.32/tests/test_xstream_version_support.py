from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addons/service.actweeter/resources'))
from lib.xstream_setup import SUPPORTED_XSTREAM_VERSIONS


def test_private_xstream_candidate_is_recognized_by_setup_gate():
    assert {'1.1.2.28~beta2', '1.1.2.28~beta3', '1.1.2.28~beta4', '1.1.2.28~beta5', '1.1.2.28~beta6', '1.1.2.28~beta7', '1.1.2.28~beta8'} <= SUPPORTED_XSTREAM_VERSIONS
