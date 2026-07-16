"""
Implements the Administrator Management workflow from the spec:

    Open Person Profile -> Click Make Administrator -> Assign Role ->
    Create Login -> Generate Temporary Password -> Send Credentials

An administrator is always created FROM an existing Person (never from
scratch), and only a Super Administrator may create one.
"""

import secrets
import string
from dataclasses import dataclass

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils.text import slugify

from apps.core.models import AuditLog
from apps.core.services import NotificationService
from apps.people.models import Person

from .models import User


class NotSuperAdminError(Exception):
    """Raised when a non-Super-Administrator attempts a Super-Administrator-only action."""


class AlreadyAdministratorError(Exception):
    """Raised when trying to promote a Person who already has an administrator account."""


def _generate_temp_password(length: int = 12) -> str:
    """A readable-but-strong temporary password: letters, digits, and a
    couple of symbols, guaranteed to include at least one of each."""
    alphabet = string.ascii_letters + string.digits
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice('!@#$%'),
    ]
    password += [secrets.choice(alphabet) for _ in range(length - len(password))]
    secrets.SystemRandom().shuffle(password)
    return ''.join(password)


def _generate_username(person: Person) -> str:
    base = slugify(f"{person.first_name}.{person.last_name}").replace('-', '.') or f"admin{person.pk}"
    username = base
    suffix = 1
    while User.objects.filter(username=username).exists():
        suffix += 1
        username = f"{base}{suffix}"
    return username


@dataclass
class NewCredentials:
    user: User
    username: str
    temporary_password: str
    email_sent: bool


class AdministratorService:

    @staticmethod
    def _require_super_admin(requested_by):
        if not getattr(requested_by, 'is_super_admin', False):
            raise NotSuperAdminError('Only the Super Administrator can manage administrator accounts.')

    @classmethod
    @transaction.atomic
    def create_administrator(cls, *, person: Person, role: str, requested_by) -> NewCredentials:
        cls._require_super_admin(requested_by)

        if User.objects.filter(person=person).exists():
            raise AlreadyAdministratorError(f"{person.full_name} already has an administrator account.")

        username = _generate_username(person)
        temp_password = _generate_temp_password()

        user = User(
            username=username,
            first_name=person.first_name,
            last_name=person.last_name,
            email=person.email_address,
            person=person,
            role=role,
            is_staff=True,
            is_superuser=(role == 'super_admin'),
            must_reset_password=True,
        )
        user.set_password(temp_password)
        user.save()

        email_sent = cls._send_credentials_email(user, temp_password)

        AuditLog.objects.create(
            administrator=requested_by,
            action=f"Created administrator '{username}' ({user.get_role_display()}) from {person.full_name} ({person.person_id})",
            model_name='User', object_id=str(user.id),
        )
        NotificationService.notify(
            title='New Administrator',
            message=f"{person.full_name} was made a {user.get_role_display()}.",
            link_url='/dashboard/administrators/',
        )

        return NewCredentials(user=user, username=username, temporary_password=temp_password, email_sent=email_sent)

    @classmethod
    def reset_password(cls, *, user: User, requested_by) -> NewCredentials:
        cls._require_super_admin(requested_by)

        temp_password = _generate_temp_password()
        user.set_password(temp_password)
        user.must_reset_password = True
        user.save(update_fields=['password', 'must_reset_password'])

        email_sent = cls._send_credentials_email(user, temp_password, is_reset=True)

        AuditLog.objects.create(
            administrator=requested_by,
            action=f"Reset password for administrator '{user.username}'",
            model_name='User', object_id=str(user.id),
        )
        return NewCredentials(user=user, username=user.username, temporary_password=temp_password, email_sent=email_sent)

    @classmethod
    def set_active(cls, *, user: User, is_active: bool, requested_by) -> User:
        cls._require_super_admin(requested_by)
        user.is_active_administrator = is_active
        user.save(update_fields=['is_active_administrator'])
        AuditLog.objects.create(
            administrator=requested_by,
            action=f"{'Reactivated' if is_active else 'Deactivated'} administrator '{user.username}'",
            model_name='User', object_id=str(user.id),
        )
        return user

    @classmethod
    def change_role(cls, *, user: User, role: str, requested_by) -> User:
        cls._require_super_admin(requested_by)
        old_role = user.get_role_display()
        user.role = role
        user.is_superuser = (role == 'super_admin')
        user.save(update_fields=['role', 'is_superuser'])
        AuditLog.objects.create(
            administrator=requested_by,
            action=f"Changed '{user.username}' role from {old_role} to {user.get_role_display()}",
            model_name='User', object_id=str(user.id),
        )
        return user

    @staticmethod
    def _send_credentials_email(user: User, temp_password: str, is_reset: bool = False) -> bool:
        if not user.email:
            return False
        subject = 'Your SEMS administrator password has been reset' if is_reset else 'Your SEMS administrator account'
        message = (
            f"Hi {user.first_name or user.username},\n\n"
            f"{'Your SEMS administrator password has been reset.' if is_reset else 'An administrator account has been created for you on SEMS.'}\n\n"
            f"Username: {user.username}\n"
            f"Temporary password: {temp_password}\n\n"
            f"You'll be asked to set a new password the first time you sign in.\n"
        )
        send_mail(
            subject, message,
            getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@sems.local'),
            [user.email], fail_silently=True,
        )
        return True
