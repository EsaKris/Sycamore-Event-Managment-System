from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedModel
from apps.events.models import Event
from apps.people.models import Person
from apps.registrations.models import Registration


class SessionType(models.TextChoices):
    MORNING = 'morning', 'Morning'
    AFTERNOON = 'afternoon', 'Afternoon'
    EVENING = 'evening', 'Evening'
    CUSTOM = 'custom', 'Custom'


class AttendanceSession(TimeStampedModel):
    """
    A single scannable window within an Event, e.g. 'Day 1 - Morning
    Service'. Per spec: supports multiple sessions a day, and check-ins
    are always scoped to one of these (never just "the event").
    """

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='attendance_sessions')
    label = models.CharField(max_length=150, help_text="e.g. 'Day 1 - Morning Service'")
    session_type = models.CharField(max_length=10, choices=SessionType.choices, default=SessionType.CUSTOM)
    date = models.DateField()
    is_active = models.BooleanField(
        default=True,
        help_text='Deactivate a session once it has ended so it drops off the scanner picker.',
    )

    class Meta:
        ordering = ['-date', '-created_at']
        constraints = [
            models.UniqueConstraint(fields=['event', 'label', 'date'], name='unique_session_per_event_day'),
        ]
        indexes = [models.Index(fields=['event', 'date'])]

    def __str__(self):
        return f"{self.event.title} — {self.label} ({self.date})"


class CheckType(models.TextChoices):
    CHECK_IN = 'check_in', 'Check-in'
    CHECK_OUT = 'check_out', 'Check-out'


class Attendance(TimeStampedModel):
    """
    A single scan event. Per spec, each scan records Person, Registration,
    Event, Session, Date, Time, Scanner, Location. Date/Time come from
    `created_at` (TimeStampedModel) rather than duplicate fields.

    The (person, session, check_type) constraint is a database-level
    backstop against double-submission races; the *friendly* "already
    checked in" messaging is handled one layer up in AttendanceService,
    which checks first so the person at the door gets a clear alert
    instead of a raw integrity error.
    """

    person = models.ForeignKey(Person, on_delete=models.PROTECT, related_name='attendance_records')
    registration = models.ForeignKey(Registration, on_delete=models.PROTECT, related_name='attendance_records')
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name='attendance_records')
    session = models.ForeignKey(AttendanceSession, on_delete=models.PROTECT, related_name='attendance_records')

    check_type = models.CharField(max_length=10, choices=CheckType.choices)
    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='scans',
    )
    location = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['person', 'session', 'check_type'], name='unique_scan_per_person_session_type'),
        ]
        indexes = [
            models.Index(fields=['session', 'check_type']),
            models.Index(fields=['event', 'created_at']),
        ]

    def __str__(self):
        return f"{self.person.full_name} - {self.get_check_type_display()} @ {self.session.label}"

    def clean(self):
        if self.registration_id and self.event_id and self.registration.event_id != self.event_id:
            raise ValidationError('Registration does not belong to this Event.')
        if self.session_id and self.event_id and self.session.event_id != self.event_id:
            raise ValidationError('Session does not belong to this Event.')
