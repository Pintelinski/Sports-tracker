"""
Settings for running the test suite.

Inherits everything from the main settings and overrides only what testing
requires: an in-memory SQLite database (so we don't need CREATEDB on Postgres),
and password hashing fast enough not to dominate test runtime.

Run with:
    python manage.py test --settings=Sportstracker.test_settings
"""

from .settings import *  # noqa: F401,F403


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Bcrypt/Argon2 are slow on purpose; tests don't care about cracking resistance.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
