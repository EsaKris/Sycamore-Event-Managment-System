"""
Automated backup — intended to run nightly via cron (no background task
queue in this project — same convention as apps.campaigns.send_due_campaigns
and apps.events.send_event_reminders).

Example crontab entry (nightly at 2am):
    0 2 * * * cd /path/to/project && /path/to/venv/bin/python manage.py backup_db >> /var/log/sems-backup.log 2>&1

The on-demand 'Download Backup Now' button in Settings (dashboard) calls
the same apps.core.backups.create_backup() — this command exists for the
unattended, scheduled case, and additionally logs an AuditLog entry so a
Super Administrator can see in Activity Logs that scheduled backups are
actually running (or when/why one failed).
"""

from django.core.management.base import BaseCommand, CommandError

from apps.core.backups import BackupError, create_backup
from apps.core.models import AuditLog


class Command(BaseCommand):
    help = 'Creates a database + media backup (see apps/core/backups.py) for cron/automation.'

    def handle(self, *args, **options):
        try:
            result = create_backup()
        except BackupError as exc:
            AuditLog.objects.create(
                administrator=None,
                action=f'Scheduled backup FAILED: {exc}',
                model_name='Backup',
            )
            raise CommandError(str(exc))

        size_mb = result.size_bytes / (1024 * 1024)
        status = 'Uploaded to S3.' if result.uploaded_to_s3 else (
            f'S3 upload failed: {result.s3_error}' if result.s3_error else 'Local only (no S3 configured).'
        )

        AuditLog.objects.create(
            administrator=None,
            action=f"Scheduled backup created ({result.path.name}, {size_mb:.1f}MB). {status}",
            model_name='Backup',
        )
        self.stdout.write(self.style.SUCCESS(
            f"Backup written to {result.path} ({size_mb:.1f}MB). {status}"
        ))
