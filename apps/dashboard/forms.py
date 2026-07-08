from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError


class AdminLoginForm(AuthenticationForm):
    """
    Identical to Django's default login form, except it also refuses
    entry to accounts that exist but have been deactivated as
    administrators (is_active_administrator=False) — the Super Admin's
    "Deactivate Account" action from the spec should take effect
    immediately without needing to touch Django's own is_active flag.
    """

    error_messages = {
        **AuthenticationForm.error_messages,
        'inactive_admin': 'This administrator account has been deactivated. Contact the Super Administrator.',
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not getattr(user, 'is_active_administrator', True):
            raise ValidationError(self.error_messages['inactive_admin'], code='inactive_admin')
