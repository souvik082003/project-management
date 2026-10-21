"""
Settings package initialization.
Defaults to development settings unless overridden by environment.
"""

from decouple import config

ENVIRONMENT = config("DJANGO_ENV", default="dev").lower()

if ENVIRONMENT == "prod" or ENVIRONMENT == "production":
    from .prod import *
else:
    from .dev import *
