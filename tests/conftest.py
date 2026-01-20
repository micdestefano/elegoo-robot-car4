#  Copyright (c) Michele De Stefano 2026.
import importlib.resources
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def resources_path() -> Path:
    return Path(str(importlib.resources.files("tests.resources")))
