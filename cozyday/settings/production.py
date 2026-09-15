import os

from .base import *

DEBUG = False

# Comma-separated list in the environment, e.g.:
#   DJANGO_ALLOWED_HOSTS=cozyday.example.com,www.cozyday.example.com
_allowed_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS", "")
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts.split(",") if h.strip()]

if not ALLOWED_HOSTS:
    raise RuntimeError(
        "DJANGO_ALLOWED_HOSTS must be set (comma-separated) when running "
        "with cozyday.settings.production."
    )