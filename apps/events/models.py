from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from apps.core.models import SoftDeleteModel, TimeStampedModel


class RegistrationStatus(models.TextChoices):
    NOT_OPEN = 'not_open', 'Not Open'
    OPEN = 'open', 'Open'
    CLOSED = 'closed', 'Closed'


class EventStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    UPCOMING = 'upcoming', 'Upcoming'
    ACTIVE = 'active', 'Active'
    COMPLETED = 'completed', 'Completed'
    ARCHIVED = 'archived', 'Archived'


def event_banner_path(instance, filename):
    return f"events/{instance.slug or 'pending'}/banner_{filename}"


def event_logo_path(instance, filename):
    return f"events/{instance.slug or 'pending'}/logo_{filename}"


class Event(TimeStampedModel, SoftDeleteModel):
    """
    A single conference/instance, e.g. 'Sycamore 2026'. This is what makes
    the system reusable year after year: nothing about Person, Department,
    or the dashboard shell is tied to a specific event — everything scopes
    through a foreign key to this model instead.
    """

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    theme = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    year = models.PositiveIntegerField(db_index=True)

    venue = models.CharField(max_length=255, blank=True)
    banner = models.ImageField(upload_to=event_banner_path, null=True, blank=True)
    logo = models.ImageField(upload_to=event_logo_path, null=True, blank=True)

    start_date = models.DateField()
    end_date = models.DateField()

    registration_open_date = models.DateTimeField(null=True, blank=True)
    registration_close_date = models.DateTimeField(null=True, blank=True)
    registration_status = models.CharField(
        max_length=10, choices=RegistrationStatus.choices, default=RegistrationStatus.NOT_OPEN,
    )

    max_capacity = models.PositiveIntegerField(null=True, blank=True, help_text='Leave blank for unlimited.')

    # Stored as a hex string, e.g. "#7C3AED" — drives the dashboard/ID-card theme for this event.
    color_theme = models.CharField(max_length=7, default='#7C3AED')

    status = models.CharField(max_length=10, choices=EventStatus.choices, default=EventStatus.DRAFT)

    class Meta:
        ordering = ['-year', '-start_date']
        indexes = [models.Index(fields=['year']), models.Index(fields=['slug'])]

    def __str__(self):
        return self.title

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError('End date cannot be before start date.')

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            if str(self.year) not in base_slug:
                base_slug = f"{base_slug}-{self.year}"
            slug = base_slug
            i = 1
            while Event.all_objects.filter(slug=slug).exclude(pk=self.pk).exists():
                i += 1
                slug = f"{base_slug}-{i}"
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def is_registration_open(self) -> bool:
        return self.registration_status == RegistrationStatus.OPEN

    @property
    def is_full(self) -> bool:
        if not self.max_capacity:
            return False
        return self.registrations.count() >= self.max_capacity
