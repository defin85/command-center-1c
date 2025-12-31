"""
CLI command catalog loader for designer_cli operations.
"""

import json
import logging
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

_CACHE: dict | None = None


def load_cli_command_catalog() -> dict:
    """
    Load CLI command catalog from config/cli_commands.json.
    Returns empty catalog if file is missing.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    catalog_path = Path(settings.BASE_DIR).parent / "config" / "cli_commands.json"
    try:
        with catalog_path.open("r", encoding="utf-8") as handle:
            _CACHE = json.load(handle)
            return _CACHE
    except FileNotFoundError:
        logger.warning("CLI command catalog not found: %s", catalog_path)
    except json.JSONDecodeError as exc:
        logger.warning("CLI command catalog is invalid: %s", exc)
    except OSError as exc:
        logger.warning("Failed to read CLI command catalog: %s", exc)

    _CACHE = {"version": "unknown", "source": str(catalog_path), "commands": []}
    return _CACHE
