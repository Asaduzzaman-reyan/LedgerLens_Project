import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from scripts.generate_fixtures import generate,FIXTURES

@pytest.fixture(scope='session',autouse=True)
def fixtures():
    if not (FIXTURES/'labels.json').exists():generate()
    return FIXTURES
