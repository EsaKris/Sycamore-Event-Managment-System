import uuid

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel
from apps.departments.models import Department
from apps.events.models import Event
from apps.people.models import Person


class TemplateType(models.TextChoices):
    """Matches the named templates the spec calls out explicitly."""

    WELCOME = 'welcome', 'Welcome Email'
    REGISTRATION_CONFIRMATION = 'registration_confirmation', 'Registration Confirmation'
    REMINDER = 'reminder', 'Reminder Email'
    ACCOMMODATION_INFO = 'accommodation_info', 'Accommodation Information'
    CONFERENCE_SCHEDULE = 'conference_schedule', 'Conference Schedule'
    THANK_YOU = 'thank_you', 'Thank You Email'
    FOLLOW_UP = 'follow_up', 'Follow-up Email'
    CUSTOM = 'custom', 'Custom'


class EmailTemplate(TimeStampedModel):
    """A reusable subject/body pair. Body may use {{ placeholders }}
    rendered through Django's own template engine — see
    apps/campaigns/services.py:CampaignService.render()."""

    name = models.CharField(max_length=150)
    template_type = models.CharField(max_length=30, choices=TemplateType.choices, default=TemplateType.CUSTOM)
    subject = models.CharField(max_length=255)
    body = models.TextField(
        help_text='Plain text or simple HTML. Use placeholders like {{ first_name }}, {{ event_title }}.',
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='email_templates',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class ReturningFilter(models.TextChoices):
    ANY = 'any', 'Anyone'
    RETURNING_ONLY = 'returning_only', 'Returning attendees only'
    FIRST_TIME_ONLY = 'first_time_only', 'First-time attendees only'


class CampaignStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    SCHEDULED = 'scheduled', 'Scheduled'
    SENDING = 'sending', 'Sending'
    SENT = 'sent', 'Sent'
    FAILED = 'failed', 'Failed'


class EmailCampaign(TimeStampedModel):
    """
    A bulk send targeting a segment of Registrations. Every field below
    that can be left blank means "no filter on this dimension" — together
    they cover every segment the spec names: Participants, Workers,
    Pastors, Departments, States, Countries, Specific Churches, Returning
    Attendees, First-Time Visitors.
    """

    name = models.CharField(max_length=150)
    template = models.ForeignKey(EmailTemplate, on_delete=models.PROTECT, related_name='campaigns')

    event = models.ForeignKey(
        Event, on_delete=models.SET_NULL, null=True, blank=True, related_name='campaigns',
        help_text='Leave blank to target across every event.',
    )
    target_category = models.CharField(max_length=15, blank=True, help_text="'participant', 'worker', or blank for both.")
    target_worker_type = models.CharField(max_length=10, blank=True, help_text="'member', 'pastor', or blank for both.")
    target_department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='campaigns',
    )
    target_state = models.CharField(max_length=100, blank=True)
    target_country = models.CharField(max_length=100, blank=True)
    target_church_name = models.CharField(max_length=255, blank=True, help_text='Matches church name (contains).')
    target_returning = models.CharField(max_length=20, choices=ReturningFilter.choices, default=ReturningFilter.ANY)

    status = models.CharField(max_length=12, choices=CampaignStatus.choices, default=CampaignStatus.DRAFT)
    scheduled_at = models.DateTimeField(
        null=True, blank=True,
        help_text='For "Send Now", leave blank. For scheduled sending, set a future time — '
                   'requires the send_due_campaigns management command to be run periodically (cron/Celery beat).',
    )
    sent_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='email_campaigns',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def is_locked(self) -> bool:
        """Once sending has started, the segment/template shouldn't change under it."""
        return self.status in (CampaignStatus.SENDING, CampaignStatus.SENT)


class RecipientStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    SENT = 'sent', 'Sent'
    FAILED = 'failed', 'Failed'
    OPENED = 'opened', 'Opened'


class CampaignRecipient(TimeStampedModel):
    """One row per Person targeted by a Campaign — gives the per-recipient
    delivery / open / failure tracking the spec asks for."""

    campaign = models.ForeignKey(EmailCampaign, on_delete=models.CASCADE, related_name='recipients')
    person = models.ForeignKey(Person, on_delete=models.PROTECT, related_name='campaign_recipient_entries')
    email_address = models.EmailField(help_text="Snapshot of the person's email at send time.")

    status = models.CharField(max_length=10, choices=RecipientStatus.choices, default=RecipientStatus.PENDING)
    sent_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    open_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        ordering = ['person__first_name']
        constraints = [
            models.UniqueConstraint(fields=['campaign', 'person'], name='unique_recipient_per_campaign'),
        ]
        indexes = [
            models.Index(fields=['campaign', 'status'], name='campaigns_recipient_status_idx'),
        ]

    def __str__(self):
        return f"{self.person.full_name} <{self.email_address}> — {self.get_status_display()}"
