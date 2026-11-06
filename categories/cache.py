"""Cache for the category list (GET /api/categories).

Why only this: it is global (the same for every user), small, read by every
client for its dropdowns and changed only by admins. Todo lists are per user
and change all the time, so caching them would mostly serve stale data.

How invalidation works: the cached list lives under a key that contains a
version number. Changing a category bumps the version, so the old entry is
simply never read again and expires by itself. No key patterns, no deletes.
"""
from django.core.cache import cache

VERSION_KEY = "categories:version"


def current_version() -> int:
    return cache.get(VERSION_KEY) or 0


def list_key(version: int) -> str:
    return f"categories:list:v{version}"


def invalidate() -> None:
    try:
        cache.incr(VERSION_KEY)
    except ValueError:  # the key does not exist yet
        cache.set(VERSION_KEY, 1, timeout=None)