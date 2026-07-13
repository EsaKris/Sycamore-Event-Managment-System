from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.events.models import Event
from apps.people.models import Person


class FollowUpType(models.TextChoices):
    """What kind of interaction this timeline entry represents. Matches
    the spec's list of things a Person's timeline should track."""

    CALL = 'call', 'Call'
    EMAIL = 'email', 'Email'
    SMS = 'sms', 'SMS'
    PRAYER_REQUEST = 'prayer_request', 'Prayer Request'
    COUNSELLING = 'counselling', 'Counselling'
    TRANSPORTATION = 'transportation', 'Transportation'
    ACCOMMODATION = 'accommodation', 'Accommodation'
    CHURCH_MEMBERSHIP = 'church_membership', 'Church Membership'
    OTHER = 'other', 'Other'


class InterestLevel(models.TextChoices):
    LOW = 'low', 'Low'
    MEDIUM = 'medium', 'Medium'
    HIGH = 'high', 'High'
    VERY_HIGH = 'very_high', 'Very High'


class FollowUpOutcome(models.TextChoices):
    PENDING = 'pending', 'Pending'
    REACHED = 'reached', 'Reached'
    NO_RESPONSE = 'no_response', 'No Response'
    RESCHEDULED = 'rescheduled', 'Rescheduled'
    RESOLVED = 'resolved', 'Resolved'


class FollowUpStatus(models.TextChoices):
    OPEN = 'open', 'Open'
    CLOSED = 'closed', 'Closed'


class FollowUp(TimeStampedModel):
    """
    One entry in a Person's follow-up timeline. Per spec: 'Every attendee
    should have a timeline' — so this is deliberately a log (many rows per
    Person over the years), not a single mutable record. `event` is
    optional context ("which conference prompted this") since follow-up
    naturally continues beyond any one event.
    """

    person = models.ForeignKey(Person, on_delete=models.PROTECT, related_name='follow_ups')
    event = models.ForeignKey(
        Event, on_delete=models.SET_NULL, null=True, blank=True, related_name='follow_ups',
        help_text='Optional — which conference this follow-up relates to.',
    )

    follow_up_type = models.CharField(max_length=20, choices=FollowUpType.choices)
    interest_level = models.CharField(max_length=10, choices=InterestLevel.choices, blank=True)
    remarks = models.TextField(blank=True)
    outcome = models.CharField(max_length=15, choices=FollowUpOutcome.choices, default=FollowUpOutcome.PENDING)
    status = models.CharField(max_length=10, choices=FollowUpStatus.choices, default=FollowUpStatus.OPEN)
    next_follow_up_date = models.DateField(null=True, blank=True)

    officer_assigned = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_followups', help_text='Who is responsible for the next step.',
    )
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='logged_followups', help_text='Who recorded this entry.',
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['person', '-created_at'], name='followup_person_created_idx'),
            models.Index(fields=['status'], name='followup_status_idx'),
            models.Index(fields=['next_follow_up_date'], name='followup_next_date_idx'),
        ]

    def __str__(self):
        return f"{self.person.full_name} — {self.get_follow_up_type_display()} ({self.created_at:%Y-%m-%d})"

    @property
    def is_overdue(self) -> bool:
        return bool(
            self.status == FollowUpStatus.OPEN
            and self.next_follow_up_date
            and self.next_follow_up_date < timezone.localdate()
        )

    def close(self, outcome: str = FollowUpOutcome.RESOLVED):
        self.status = FollowUpStatus.CLOSED
        self.outcome = outcome
        self.save(update_fields=['status', 'outcome', 'updated_at'])
