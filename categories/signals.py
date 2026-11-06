from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from . import cache
from .models import Category


@receiver([post_save, post_delete], sender=Category, dispatch_uid="category_cache_invalidate")
def invalidate_category_cache(sender, **kwargs):
    # After the commit, not before: the admin saves inside a transaction. If we
    # bumped the version first, a request could read the old row, cache it under
    # the new version, and serve it until the entry expires.
    transaction.on_commit(cache.invalidate)