"""Settings for creating migrations without DB connection."""
# ruff: noqa: F403
from .base import *

# Override database to use SQLite
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
