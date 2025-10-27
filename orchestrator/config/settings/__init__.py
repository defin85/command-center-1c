# Settings package
import os

# По умолчанию используем development settings для тестов
env = os.environ.get('DJANGO_ENV', 'development')

if env == 'production':
    from .production import *
else:
    from .development import *
