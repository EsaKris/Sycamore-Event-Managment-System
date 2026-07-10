import uuid

from django.conf import settings
from django.db import models, transaction

from apps.core.models import SoftDeleteModel, TimeStampedModel


class Gender(models.TextChoices):
    MALE = 'male', 'Male'
    FEMALE = 'female', 'Female'


class MaritalStatus(models.TextChoices):
    SINGLE = 'single', 'Single'
    MARRIED = 'married', 'Married'
    DIVORCED = 'divorced', 'Divorced'
    WIDOWED = 'widowed', 'Widowed'


class PersonStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'
    FLAGGED = 'flagged', 'Flagged'  # e.g. suspected duplicate pending review


def _next_person_id() -> str:
    """
    Generates the next permanent, sequential Person ID, e.g. SYC-000001.

    Wrapped in select_for_update() by the caller (see Person.save) so two
    concurrent registrations can't ever be handed the same number.
    """
    prefix = settings.SEMS_PERSON_ID_PREFIX
    digits = settings.SEMS_PERSON_ID_DIGITS
    last = Person.all_objects.select_for_update().order_by('-id').first()
    next_number = (last.id + 1) if last else 1
    return f"{prefix}-{str(next_number).zfill(digits)}"


def person_photo_path(instance, filename):
    ext = filename.split('.')[-1]
    return f"people/photos/{instance.person_id or 'pending'}/{uuid.uuid4().hex}.{ext}"


class Person(TimeStampedModel, SoftDeleteModel):
    """
    The single permanent source of truth for a human being in SEMS.

    THE CORE RULE OF THIS SYSTEM: a Person is created ONCE, ever. Every
    subsequent conference/event they attend creates a new Registration
    pointing back at this same row — never a new Person. See
    apps/people/services.py for the matching logic that enforces this
    during the registration flow.
    """

    # Permanent identity
    person_id = models.CharField(max_length=20, unique=True, editable=False, db_index=True)
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    # Photo
    photo = models.ImageField(upload_to=person_photo_path, null=True, blank=True)

    # Names
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)

    # Demographics
    gender = models.CharField(max_length=10, choices=Gender.choices)
    date_of_birth = models.DateField(null=True, blank=True)
    marital_status = models.CharField(max_length=10, choices=MaritalStatus.choices, blank=True)

    # Contact — phone is the primary de-dup key, so it's indexed and required
    phone_number = models.CharField(max_length=20, db_index=True)
    alternative_phone = models.CharField(max_length=20, blank=True)
    email_address = models.EmailField(blank=True, db_index=True)

    # Address
    residential_address = models.TextField(blank=True)
    state = models.CharField(max_length=100, blank=True)
    local_government = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Nigeria')

    # Church affiliation
    church_name = models.CharField(max_length=255, blank=True)
    church_address = models.TextField(blank=True)
    pastors_name = models.CharField(max_length=255, blank=True)

    # Other profile info
    occupation = models.CharField(max_length=255, blank=True)

    # Emergency contact
    emergency_contact_name = models.CharField(max_length=255, blank=True)
    emergency_phone = models.CharField(max_length=20, blank=True)
    emergency_relationship = models.CharField(max_length=100, blank=True)

    # Optional notes
    medical_notes = models.TextField(blank=True)
    dietary_notes = models.TextField(blank=True)

    status = models.CharField(max_length=10, choices=PersonStatus.choices, default=PersonStatus.ACTIVE)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone_number']),
            models.Index(fields=['email_address']),
            models.Index(fields=['person_id']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.person_id})"

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.middle_name, self.last_name]
        return ' '.join(p for p in parts if p)

    @property
    def qr_payload(self) -> str:
        """The exact string encoded into this person's QR code. Prefixed
        so a scanner can tell a SEMS code apart from an unrelated QR
        someone might scan by mistake."""
        return f"SEMS:{self.qr_token}"

    def save(self, *args, **kwargs):
        if not self.person_id:
            with transaction.atomic():
                self.person_id = _next_person_id()
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Hard delete is blocked at the model layer. Per spec, a Person
        record is never destroyed except explicitly by a Super
        Administrator — that authorization check belongs in the service/
        view layer (apps/people/services.py), not here. This override
        exists as a last line of defense against an accidental .delete()
        call anywhere else in the codebase.
        """
        raise RuntimeError(
            'Person records cannot be hard-deleted directly. '
            'Use PersonService.delete_person(person, requested_by=<super admin>) instead.'
        )
