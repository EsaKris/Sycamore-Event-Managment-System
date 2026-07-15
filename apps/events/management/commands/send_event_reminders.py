"""
Creates an 'Upcoming Event' notification for events starting soon.
Intended to run daily via cron (no background task queue in this
project — same convention as apps.campaigns.send_due_campaigns).

Reminder milestones: 7 days out and 1 day out. Idempotent — re-running
this command the same day (or any day that isn't exactly a milestone)
does nothing, and each event+milestone pair only ever notifies once,
tracked via a `reminder=<days>d` marker embedded in the notification's
link_url rather than a new model field.

Example crontab entry (once a day, 7am):
    0 7 * * * cd /path/to/project && python manage.py send_event_reminders
"""

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.core.models import Notification
from apps.core.services import NotificationService
from apps.events.models import Event, EventStatus

REMINDER_DAYS = [7, 1]


class Command(BaseCommand):
    help = "Sends 'Upcoming Event' notifications for events starting in 7 or 1 day(s)."

    def handle(self, *args, **options):
        today = timezone.localdate()
        created = 0

        events = Event.objects.exclude(status__in=[EventStatus.COMPLETED, EventStatus.ARCHIVED])
        for event in events:
            days_until = (event.start_date - today).days
            if days_until not in REMINDER_DAYS:
                continue

            marker = f'reminder={days_until}d'
            already_sent = Notification.objects.filter(
                Q(link_url__contains=f'event={event.id}&') & Q(link_url__contains=marker),
            ).exists()
            if already_sent:
                continue

            link_url = f'/dashboard/attendance/scanner/?event={event.id}&{marker}'

            when = 'tomorrow' if days_until == 1 else f'in {days_until} days'
            NotificationService.notify(
                title='Upcoming Event',
                message=f"{event.title} starts {when} ({event.start_date:%b %d, %Y}).",
                link_url=link_url,
            )
            created += 1
            self.stdout.write(self.style.SUCCESS(f"Notified: {event.title} ({when})"))

        if not created:
            self.stdout.write('No event reminders due today.')
        else:
            self.stdout.write(self.style.SUCCESS(f"Done — {created} reminder(s) created."))
