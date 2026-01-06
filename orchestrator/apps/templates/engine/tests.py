"""
Custom Jinja2 tests for conditional logic.

IMPORTANT: These are Jinja2 "tests", NOT unit tests!
Jinja2 tests are used in {% if %} conditions like:
    {% if database is production_database %}...{% endif %}
"""

__test__ = False


def register_custom_tests(env):
    """Register all custom tests."""
    env.tests['production_database'] = test_production_database
    env.tests['test_database'] = test_test_database
    env.tests['development_database'] = test_development_database
    env.tests['empty'] = test_empty
    env.tests['nonempty'] = test_nonempty


def test_production_database(database):
    """
    Test if database is production type.

    Usage in template:
        {% if database is production_database %}
        ...production logic...
        {% endif %}

    Args:
        database: Database dict or object with 'type' attribute

    Returns:
        True if database type is 'production', False otherwise
    """
    if isinstance(database, dict):
        return database.get('type') == 'production'
    # If database is Django model
    return getattr(database, 'type', None) == 'production'


def test_test_database(database):
    """
    Test if database is test type.

    Usage in template:
        {% if database is test_database %}
        ...test logic...
        {% endif %}

    Args:
        database: Database dict or object with 'type' attribute

    Returns:
        True if database type is 'test', False otherwise
    """
    if isinstance(database, dict):
        return database.get('type') == 'test'
    return getattr(database, 'type', None) == 'test'


def test_development_database(database):
    """
    Test if database is development type.

    Usage in template:
        {% if database is development_database %}
        ...dev logic...
        {% endif %}

    Args:
        database: Database dict or object with 'type' attribute

    Returns:
        True if database type is 'development', False otherwise
    """
    if isinstance(database, dict):
        return database.get('type') == 'development'
    return getattr(database, 'type', None) == 'development'


def test_empty(value):
    """
    Test if value is empty (None, '', [], {}, 0).

    Usage:
        {% if user_list is empty %}
        No users found
        {% endif %}

    Args:
        value: Any value to check

    Returns:
        True if value is considered empty, False otherwise

    Note:
        False and True are NOT considered empty (they are valid boolean values).
        Only None, empty collections, empty string, and 0 are empty.
    """
    if value is None:
        return True

    # IMPORTANT: Check bool BEFORE int (bool is subclass of int in Python!)
    if isinstance(value, bool):
        return False  # Booleans are never empty

    if isinstance(value, (str, list, dict)):
        return len(value) == 0
    if isinstance(value, (int, float)):
        return value == 0
    return False


def test_nonempty(value):
    """
    Test if value is not empty.

    Usage:
        {% if user_list is nonempty %}
        Found {{ user_list|length }} users
        {% endif %}

    Args:
        value: Any value to check

    Returns:
        True if value is not empty, False otherwise
    """
    return not test_empty(value)
