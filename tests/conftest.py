from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rpra.reproduction import compute_public_results, load_all_configurations


@pytest.fixture(scope="session")
def public_results():
    return compute_public_results(ROOT)


@pytest.fixture(scope="session")
def configurations():
    return load_all_configurations(ROOT)

