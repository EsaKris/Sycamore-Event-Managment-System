"""
Event lifecycle actions that need more than a plain field edit: opening/
closing registration and archiving fire the same explicit
AuditLog + Notification pattern used across every other service in this
codebase. Plain attribute edits (title, dates, banner, ...) go through
EventForm directly — this module is only for the actions that mean
something happens as a result.
"""

from django.utils import timezone

from apps.core.models import AuditLog
from apps.core.services import NotificationService

from .models import Event, EventStatus, RegistrationStatus


class EventService:

    @staticmethod
    def open_registration(event: Event, *, requested_by) -> Event:
        event.registration_status = RegistrationStatus.OPEN
        if not event.registration_open_date:
            event.registration_open_date = timezone.now()
        event.save(update_fields=['registration_status', 'registration_open_date'])

        AuditLog.objects.create(
            administrator=requested_by, action=f"Opened registration for '{event.title}'",
            model_name='Event', object_id=event.id,
        )
        return event

    @staticmethod
    def close_registration(event: Event, *, requested_by) -> Event:
        event.registration_status = RegistrationStatus.CLOSED
        event.registration_close_date = timezone.now()
        event.save(update_fields=['registration_status', 'registration_close_date'])

        AuditLog.objects.create(
            administrator=requested_by, action=f"Closed registration for '{event.title}'",
            model_name='Event', object_id=event.id,
        )
        NotificationService.notify(
            title='Registration Closed',
            message=f"Registration for {event.title} is now closed. {event.registrations.count()} total registrations.",
            link_url=f'/dashboard/events/{event.id}/',
        )
        return event

    @staticmethod
    def set_status(event: Event, status: str, *, requested_by) -> Event:
        old = event.get_status_display()
        event.status = status
        event.save(update_fields=['status'])
        AuditLog.objects.create(
            administrator=requested_by, action=f"Changed '{event.title}' status from {old} to {event.get_status_display()}",
            model_name='Event', object_id=event.id,
        )
        return event

    @staticmethod
    def archive(event: Event, *, requested_by) -> Event:
        return EventService.set_status(event, EventStatus.ARCHIVED, requested_by=requested_by)
