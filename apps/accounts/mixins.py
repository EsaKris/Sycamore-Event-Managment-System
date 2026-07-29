from functools import wraps

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class SuperAdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restricts a view to the Super Administrator, per spec: 'Only the
    Super Administrator can create administrators.' Applied to the whole
    Administrator Management area, not just creation, since role changes
    and deactivation carry the same authority requirement."""

    login_url = 'dashboard:login'
    raise_exception = False  # redirect to login/forbidden page rather than a bare 403

    def test_func(self):
        return getattr(self.request.user, 'is_super_admin', False)

    def handle_no_permission(self):
        from django.contrib import messages
        from django.shortcuts import redirect
        if self.request.user.is_authenticated:
            messages.error(self.request, "Only the Super Administrator can access Administrator Management.")
            return redirect('dashboard:home')
        return super().handle_no_permission()


class RolesRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    General-purpose role gate for class-based views — every dashboard view
    up to now only checked 'are you logged in', not 'does your role allow
    this'. Subclass and set `allowed_roles` (an iterable of
    apps.accounts.models.AdminRole values); the Super Administrator always
    passes regardless of what's listed, since they're the top of the
    hierarchy everywhere else in this app.

    Usage:
        class CampaignListView(RolesRequiredMixin, ListView):
            allowed_roles = {AdminRole.MEDIA_OFFICER}
            ...
    """

    login_url = 'dashboard:login'
    allowed_roles: set = frozenset()
    forbidden_message = "You don't have permission to access this area."

    def test_func(self):
        user = self.request.user
        return getattr(user, 'is_super_admin', False) or getattr(user, 'role', None) in self.allowed_roles

    def handle_no_permission(self):
        from django.contrib import messages
        from django.shortcuts import redirect
        if self.request.user.is_authenticated:
            messages.error(self.request, self.forbidden_message)
            return redirect('dashboard:home')
        return super().handle_no_permission()


def roles_required(*allowed_roles, message="You don't have permission to access this area."):
    """
    Function-view counterpart to RolesRequiredMixin, for the
    @login_required-style function-based views elsewhere in the app
    (e.g. apps/campaigns/views.py). The Super Administrator always passes.

    Usage:
        @login_required(login_url='dashboard:login')
        @roles_required(AdminRole.MEDIA_OFFICER)
        def campaign_send(request, pk):
            ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            from django.contrib import messages
            from django.shortcuts import redirect

            user = request.user
            if not (getattr(user, 'is_super_admin', False) or getattr(user, 'role', None) in allowed_roles):
                if user.is_authenticated:
                    messages.error(request, message)
                    return redirect('dashboard:home')
                return redirect('dashboard:login')
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
