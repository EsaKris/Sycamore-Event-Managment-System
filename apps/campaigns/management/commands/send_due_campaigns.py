"""
Sends any campaign whose `scheduled_at` has arrived. Intended to be run
periodically (cron / Celery beat / etc.) — this project has no background
task queue, so "Scheduling" a campaign means it sits with status=SCHEDULED
until something runs this command; "Send Now" from the dashboard bypasses
scheduling entirely and sends synchronously in-request.

Example crontab entry (every 5 minutes):
    */5 * * * * cd /path/to/project && python manage.py send_due_campaigns
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.campaigns.models import CampaignStatus, EmailCampaign
from apps.campaigns.services import CampaignService


class Command(BaseCommand):
    help = 'Sends all scheduled campaigns whose scheduled_at time has passed.'

    def handle(self, *args, **options):
        due = EmailCampaign.objects.filter(
            status=CampaignStatus.SCHEDULED,
            scheduled_at__lte=timezone.now(),
        )
        count = due.count()
        if not count:
            self.stdout.write('No campaigns due.')
            return

        for campaign in due:
            self.stdout.write(f"Sending '{campaign.name}' (id={campaign.pk})…")
            result = CampaignService.send_campaign(campaign)
            self.stdout.write(self.style.SUCCESS(
                f"  -> {result['sent']} sent, {result['failed']} failed",
            ))

        self.stdout.write(self.style.SUCCESS(f"Done — {count} campaign(s) processed."))
