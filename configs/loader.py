"""Single loader for configs/project_config.yaml.

Every script that used to hardcode a path or a quality threshold in its own
argparse defaults should import from here instead, so there is exactly one
place to look when a path or threshold needs to change (Module 0, step 5).
"""

from functools import lru_cache
from pathlib import Path

import yaml

_CONFIG_PATH = Path(__file__).resolve().parent / "project_config.yaml"


@lru_cache(maxsize=1)
def load_config() -> dict:
    """Load and cache configs/project_config.yaml."""
    with _CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def get_path(key: str) -> str:
    """Look up a value under the top-level "paths" section."""
    return load_config()["paths"][key]
