from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.models import TimeStampedModel


class AdminRole(models.TextChoices):
    SUPER_ADMIN = 'super_admin', 'Super Administrator'
    REGISTRATION_OFFICER = 'registration_officer', 'Registration Officer'
    ATTENDANCE_OFFICER = 'attendance_officer', 'Attendance Officer'
    MEDIA_OFFICER = 'media_officer', 'Media Officer'
    FOLLOWUP_OFFICER = 'followup_officer', 'Follow-up Officer'
    DEPARTMENT_COORDINATOR = 'department_coordinator', 'Department Coordinator'


class User(AbstractUser, TimeStampedModel):
    """
    Administrators ONLY. Per spec: attendees, workers, and pastors never
    get login accounts — only staff who need dashboard access do.

    An administrator is always created *from* an existing Person record
    (Person Profile -> "Make Administrator" -> assign role -> create
    login), hence the required OneToOne link below. The Person model
    itself has no idea User exists (people app does not import accounts),
    keeping the dependency one-directional.
    """

    person = models.OneToOneField(
        'people.Person',
        on_delete=models.PROTECT,
        related_name='administrator_account',
        null=True,
        blank=True,
        help_text='The Person record this administrator account was created from.',
    )
    role = models.CharField(max_length=30, choices=AdminRole.choices, default=AdminRole.REGISTRATION_OFFICER)
    must_reset_password = models.BooleanField(
        default=True,
        help_text='True until the administrator changes their auto-generated temporary password.',
    )
    is_active_administrator = models.BooleanField(
        default=True,
        help_text='Soft on/off switch distinct from Django is_active, so Super Admin can '
                   'deactivate/reactivate without touching auth internals.',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_super_admin(self):
        return self.role == AdminRole.SUPER_ADMIN or self.is_superuser
