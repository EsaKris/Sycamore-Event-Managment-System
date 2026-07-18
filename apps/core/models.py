import uuid

from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """Adds created/updated timestamps to any model."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """Adds a public-facing UUID, separate from the numeric primary key.

    Used anywhere we don't want to expose sequential integer IDs
    (e.g. in QR codes or public URLs).
    """

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager):
    """Default manager only returns non-deleted rows."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)


class SoftDeleteModel(models.Model):
    """
    Soft-delete support, per spec: Person records must never be hard-deleted
    except by the Super Administrator. Same pattern is reused for Events,
    Departments, etc. where archiving (not destroying) is the safe default.
    """

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()  # bypasses the soft-delete filter

    class Meta:
        abstract = True

    def soft_delete(self):
        from django.utils import timezone
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])


class AuditLog(TimeStampedModel):
    """
    The audit trail backing the Activity Logs page (apps/dashboard).
    Written to from service-layer methods across the codebase (never from
    templates or ad-hoc view code) so every mutating action has a
    consistent record: who, what, on which record, from where.
    """

    administrator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=255)
    model_name = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=100, blank=True)
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['model_name']),
        ]

    def __str__(self):
        return f"{self.administrator} - {self.action} ({self.created_at:%Y-%m-%d %H:%M})"


class NotificationLevel(models.TextChoices):
    INFO = 'info', 'Info'
    SUCCESS = 'success', 'Success'
    WARNING = 'warning', 'Warning'
    ERROR = 'error', 'Error'


class Notification(TimeStampedModel):
    """
    Per spec: 'Real-time notifications' — New Registration, New
    Administrator, Registration Closed, Email Failed, Upcoming Event, etc.

    Broadcast-style rather than per-recipient rows: one Notification is
    visible to every administrator, and read-state is tracked per-admin
    via the `read_by` M2M. This avoids fanning out N duplicate rows at
    creation time for what's a small admin team by nature (a handful of
    people running one conference), and keeps "mark all read" a single
    query instead of a bulk-create.
    """

    level = models.CharField(max_length=10, choices=NotificationLevel.choices, default=NotificationLevel.INFO)
    title = models.CharField(max_length=150)
    message = models.CharField(max_length=500, blank=True)
    link_url = models.CharField(max_length=255, blank=True)

    read_by = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='read_notifications')

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['-created_at'])]

    def __str__(self):
        return self.title

    def is_read_by(self, user) -> bool:
        return self.read_by.filter(pk=getattr(user, 'pk', None)).exists()


class SystemSettings(models.Model):
    """
    Singleton (enforced via pk=1 in `load()`/`save()`) holding the
    site-wide configuration that's actually safe and sensible to store in
    the database and edit from a UI.

    Deliberately does NOT include SMTP credentials or the Person-ID
    prefix/digit-count: those live in environment variables (see
    config/settings.py) on purpose — secrets don't belong in a
    database an administrator can edit from a web form, and the ID
    prefix/format is baked into every already-issued Person ID, so
    changing it at runtime without a migration plan would be actively
    dangerous. The Settings page surfaces both as read-only for visibility.
    """

    system_name = models.CharField(max_length=100, default='SEMS')
    church_name = models.CharField(max_length=150, default='Again and Afresh Church')
    church_logo = models.ImageField(upload_to='settings/', null=True, blank=True)
    support_email = models.EmailField(blank=True)
    default_color_theme = models.CharField(max_length=7, default='#D4A24C')
    default_theme_mode = models.CharField(
        max_length=5, choices=[('dark', 'Dark'), ('light', 'Light')], default='dark',
    )
    giving_url = models.URLField(
        blank=True,
        help_text="Where the public site's 'Give' button links to (e.g. a Paystack payment "
                   "link or your existing giving page). Registration itself is always free — "
                   "this is a voluntary link, not a payment gate. Leave blank to hide the button.",
    )

    default_event = models.ForeignKey(
        'events.Event', null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
        help_text="Which event '/register/' and the public landing page resolve to when no "
                   "slug is given — this is what makes the short, shareable URL possible "
                   "(e.g. sycamore.againandafresh.org/register instead of /register/sycamore-2026/). "
                   "Event-specific links (/register/<slug>/) keep working regardless, so other "
                   "concurrent events can still be shared directly. Leave blank if nothing should "
                   "resolve at the short URL yet.",
    )

    updated_at = models.DateTimeField(auto_now=True)


    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # singleton — deletion is a no-op rather than an error, so stray calls don't 500

    @classmethod
    def load(cls) -> 'SystemSettings':
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return self.system_name
