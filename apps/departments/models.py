from django.db import models

from apps.core.models import SoftDeleteModel, TimeStampedModel


class Department(TimeStampedModel, SoftDeleteModel):
    """
    Departments are global (not per-event) so history/continuity carries
    across years — e.g. the same 'Media' department exists for Sycamore
    2026, 2027, 2028. Coordinators and rosters are still scoped per-event
    through Registration/Worker records, not here.
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
