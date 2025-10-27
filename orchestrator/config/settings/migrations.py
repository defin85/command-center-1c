"""Settings for creating migrations without DB connection."""
from .base import *

# Override database to use SQLite
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
