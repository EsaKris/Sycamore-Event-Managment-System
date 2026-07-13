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
