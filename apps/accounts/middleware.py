from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordResetMiddleware:
    """
    Closes the loop on the 'Generate Temporary Password' step: an
    administrator logging in with a temp password (must_reset_password=True)
    is redirected to the password-change screen before they can reach
    anything else in the dashboard. Login/logout/static/the change-password
    view itself are exempt so the redirect can't loop.
    """

    EXEMPT_PREFIXES = ('/dashboard/login/', '/dashboard/logout/', '/dashboard/change-password/', '/static/', '/media/', '/sys-admin/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if (
            user and user.is_authenticated
            and getattr(user, 'must_reset_password', False)
            and not request.path.startswith(self.EXEMPT_PREFIXES)
        ):
            return redirect(reverse('dashboard:change_password'))
        return self.get_response(request)
