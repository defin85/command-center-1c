"""
Template Library - готовые шаблоны для типовых операций.

Использование:
    from apps.templates.library import get_template_library

    templates = get_template_library()
    catalog_users = templates['catalog_users']
"""

import json
from pathlib import Path
from typing import Dict, Any

LIBRARY_DIR = Path(__file__).parent


def get_template_library() -> Dict[str, Dict[str, Any]]:
    """
    Load all templates from library.

    Returns:
        Dict mapping template name to template data
    """
    templates = {}

    for json_file in LIBRARY_DIR.glob('*.json'):
        template_name = json_file.stem  # filename without .json

        with open(json_file, 'r', encoding='utf-8') as f:
            template_data = json.load(f)
            templates[template_name] = template_data

    return templates


def load_template(template_name: str) -> Dict[str, Any]:
    """
    Load specific template from library.

    Args:
        template_name: Name of template (e.g., 'catalog_users')

    Returns:
        Template data dict

    Raises:
        FileNotFoundError: If template doesn't exist
    """
    template_path = LIBRARY_DIR / f"{template_name}.json"

    if not template_path.exists():
        raise FileNotFoundError(f"Template '{template_name}' not found in library")

    with open(template_path, 'r', encoding='utf-8') as f:
        return json.load(f)
