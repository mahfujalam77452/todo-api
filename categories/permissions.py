from rest_framework.permissions import SAFE_METHODS, DjangoModelPermissions


class CategoryPermissions(DjangoModelPermissions):
    """Anyone signed in may read categories; only admins may change them.

    "Admin" means the same thing here as in the admin site: an active staff
    user holding the Django permission for the action (add_category for POST,
    change_category for PATCH, delete_category for DELETE). A superuser holds
    all of them. So whoever can edit categories in /admin/ can do it through
    the API, and nobody else can.

    Not signed in is a 401 (DRF asks for authentication first); signed in but
    not an admin is a 403.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):  # signed in + model permission
            return False
        return request.method in SAFE_METHODS or bool(request.user.is_staff)