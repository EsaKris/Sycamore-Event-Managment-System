from django.core.exceptions import ValidationError
from django.db import models, transaction

from apps.core.models import TimeStampedModel
from apps.departments.models import Department
from apps.events.models import Event
from apps.people.models import Person


class RegistrationCategory(models.TextChoices):
    PARTICIPANT = 'participant', 'Participant'
    WORKER = 'worker', 'Worker'


class WorkerType(models.TextChoices):
    MEMBER = 'member', 'Member'
    PASTOR = 'pastor', 'Pastor'


class RegistrationStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    CONFIRMED = 'confirmed', 'Confirmed'
    CANCELLED = 'cancelled', 'Cancelled'
    WAITLISTED = 'waitlisted', 'Waitlisted'


def _next_registration_number(event: Event) -> str:
    """
    Per-event sequential registration number, e.g. SYC2026-000001.
    Caller runs this inside an atomic block with the event row locked
    (see Registration.save) to avoid a race between two simultaneous
    registrations at a busy front desk.
    """
    year_part = event.year
    prefix = f"SYC{year_part}"
    last = (
        Registration.objects.select_for_update()
        .filter(event=event)
        .order_by('-id')
        .first()
    )
    next_number = (last.id + 1) if last else 1
    return f"{prefix}-{str(next_number).zfill(6)}"


class Registration(TimeStampedModel):
    """
    A Person's participation in one specific Event. This is the row that
    gets created fresh every year — Person never is (see apps/people).
    """

    person = models.ForeignKey(Person, on_delete=models.PROTECT, related_name='registrations')
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name='registrations')

    registration_number = models.CharField(max_length=30, unique=True, editable=False)

    category = models.CharField(max_length=15, choices=RegistrationCategory.choices)
    worker_type = models.CharField(max_length=10, choices=WorkerType.choices, blank=True)
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='registrations',
    )

    is_returning_attendee = models.BooleanField(
        default=False,
        help_text="Answer to 'Have you attended any previous Sycamore Conference?' for this registration.",
    )

    accommodation_requested = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=RegistrationStatus.choices, default=RegistrationStatus.PENDING)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            # A Person can only have ONE registration per Event — re-registering
            # for the same conference should edit the existing row, not create a new one.
            models.UniqueConstraint(fields=['person', 'event'], name='unique_person_per_event'),
        ]
        indexes = [models.Index(fields=['registration_number'])]

    def __str__(self):
        return f"{self.person.full_name} - {self.event.title} ({self.registration_number})"

    def clean(self):
        if self.category == RegistrationCategory.WORKER and not self.worker_type:
            raise ValidationError({'worker_type': 'Worker type (Member/Pastor) is required for worker registrations.'})
        if self.category == RegistrationCategory.PARTICIPANT and self.worker_type:
            raise ValidationError({'worker_type': 'Participants should not have a worker type.'})
        if self.category == RegistrationCategory.WORKER and not self.department_id:
            raise ValidationError({'department': 'Workers must be assigned to a department.'})

    def save(self, *args, **kwargs):
        self.full_clean(exclude=[f.name for f in self._meta.fields if f.name not in
                                  ('category', 'worker_type', 'department')])
        if not self.registration_number:
            with transaction.atomic():
                # Lock the event row so two simultaneous saves can't compute the same number.
                Event.objects.select_for_update().get(pk=self.event_id)
                self.registration_number = _next_registration_number(self.event)
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)
