from rest_framework.permissions import BasePermission


class IsActiveAdministrator(BasePermission):
    """
    A valid auth token isn't enough on its own — the middleware that
    normally enforces `is_active_administrator` for the dashboard is
    session-based and doesn't run for token-authenticated API requests,
    so this permission re-checks it explicitly. A Super Administrator
    deactivating someone should cut off their API access too, not just
    their browser session.
    """

    message = 'This administrator account has been deactivated.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active_administrator)


class IsSuperAdministrator(BasePermission):
    message = 'Only the Super Administrator can do that.'

    def has_permission(self, request, view):
        return bool(getattr(request.user, 'is_super_admin', False))
