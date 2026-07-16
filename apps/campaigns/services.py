"""
Email Campaigns business logic:
    - Segment building (turns an EmailCampaign's target_* filters into the
      matching Registrations/Person recipients)
    - Placeholder rendering, via Django's own template engine so
      {{ first_name }} etc. just work
    - Sending, with per-recipient failure isolation (one bad address
      doesn't sink the whole batch) and an embedded open-tracking pixel
"""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import Context, Template
from django.utils import timezone

from apps.registrations.models import Registration

from .models import CampaignRecipient, CampaignStatus, RecipientStatus, ReturningFilter


class CampaignService:

    @staticmethod
    def build_segment(campaign):
        """Registrations matching this campaign's targeting filters.
        Registration (not Person) is the base queryset because most
        filters — category, department, returning-status — describe a
        specific event registration, not the permanent Person record."""
        qs = (
            Registration.objects.select_related('person', 'department', 'event')
            .exclude(person__email_address='')
        )
        if campaign.event_id:
            qs = qs.filter(event_id=campaign.event_id)
        if campaign.target_category:
            qs = qs.filter(category=campaign.target_category)
        if campaign.target_worker_type:
            qs = qs.filter(worker_type=campaign.target_worker_type)
        if campaign.target_department_id:
            qs = qs.filter(department_id=campaign.target_department_id)
        if campaign.target_state:
            qs = qs.filter(person__state__iexact=campaign.target_state)
        if campaign.target_country:
            qs = qs.filter(person__country__iexact=campaign.target_country)
        if campaign.target_church_name:
            qs = qs.filter(person__church_name__icontains=campaign.target_church_name)
        if campaign.target_returning == ReturningFilter.RETURNING_ONLY:
            qs = qs.filter(is_returning_attendee=True)
        elif campaign.target_returning == ReturningFilter.FIRST_TIME_ONLY:
            qs = qs.filter(is_returning_attendee=False)
        return qs

    @classmethod
    def sync_recipients(cls, campaign) -> int:
        """(Re-)builds the recipient list for a still-draft/scheduled
        campaign. Idempotent — safe to call repeatedly as filters are
        tweaked. A campaign that has already started sending keeps its
        historical recipient list untouched (that list is now a record
        of what actually happened, not a live query)."""
        if campaign.is_locked:
            return campaign.recipients.count()

        wanted = {}
        for reg in cls.build_segment(campaign).iterator():
            wanted.setdefault(reg.person_id, reg.person.email_address)

        existing_ids = set(campaign.recipients.values_list('person_id', flat=True))

        to_create = [
            CampaignRecipient(campaign=campaign, person_id=pid, email_address=email)
            for pid, email in wanted.items() if pid not in existing_ids
        ]
        if to_create:
            CampaignRecipient.objects.bulk_create(to_create)

        stale_ids = existing_ids - set(wanted.keys())
        if stale_ids:
            campaign.recipients.filter(person_id__in=stale_ids, status=RecipientStatus.PENDING).delete()

        return campaign.recipients.count()

    @staticmethod
    def render(template_text: str, person, registration=None, event=None) -> str:
        context = {
            'first_name': person.first_name,
            'last_name': person.last_name,
            'full_name': person.full_name,
            'person_id': person.person_id,
            'church_name': person.church_name,
            'phone_number': person.phone_number,
        }
        if registration:
            context.update({
                'registration_number': registration.registration_number,
                'category': registration.get_category_display(),
                'department': registration.department.name if registration.department else '',
                'event_title': registration.event.title,
            })
        elif event:
            context['event_title'] = event.title
        return Template(template_text).render(Context(context, autoescape=False))

    @staticmethod
    def _base_url(request) -> str:
        if request is not None:
            return request.build_absolute_uri('/').rstrip('/')
        return getattr(settings, 'SEMS_SITE_URL', '').rstrip('/')

    @classmethod
    def send_campaign(cls, campaign, request=None) -> dict:
        """Synchronous send — fine for the recipient volumes a single
        church conference realistically produces. For much larger lists,
        wire this same method into a background task runner instead of
        calling it inline from a view."""
        cls.sync_recipients(campaign)
        campaign.status = CampaignStatus.SENDING
        campaign.save(update_fields=['status'])

        base_url = cls._base_url(request)
        sent, failed = 0, 0

        pending = campaign.recipients.filter(
            status__in=[RecipientStatus.PENDING, RecipientStatus.FAILED],
        ).select_related('person')

        for recipient in pending:
            registration = (
                Registration.objects.filter(person=recipient.person, event_id=campaign.event_id).first()
                if campaign.event_id else
                Registration.objects.filter(person=recipient.person).order_by('-created_at').first()
            )
            try:
                subject = cls.render(campaign.template.subject, recipient.person, registration=registration, event=campaign.event)
                body = cls.render(campaign.template.body, recipient.person, registration=registration, event=campaign.event)

                html_body = body
                if base_url:
                    pixel = (
                        f'<img src="{base_url}/dashboard/campaigns/track/{recipient.open_token}.gif" '
                        f'width="1" height="1" alt="" style="display:none">'
                    )
                    html_body = f"{body}{pixel}"

                message = EmailMultiAlternatives(
                    subject=subject, body=body, from_email=settings.DEFAULT_FROM_EMAIL, to=[recipient.email_address],
                )
                message.attach_alternative(html_body, 'text/html')
                message.send(fail_silently=False)

                recipient.status = RecipientStatus.SENT
                recipient.sent_at = timezone.now()
                recipient.error_message = ''
                recipient.save(update_fields=['status', 'sent_at', 'error_message', 'updated_at'])
                sent += 1
            except Exception as exc:  # noqa: BLE001 — one bad recipient must never abort the batch
                recipient.status = RecipientStatus.FAILED
                recipient.error_message = str(exc)[:500]
                recipient.save(update_fields=['status', 'error_message', 'updated_at'])
                failed += 1

        if campaign.recipients.count() == 0 or sent > 0:
            campaign.status = CampaignStatus.SENT
        else:
            campaign.status = CampaignStatus.FAILED
        campaign.sent_at = timezone.now()
        campaign.save(update_fields=['status', 'sent_at'])

        if failed > 0:
            from apps.core.services import NotificationService
            NotificationService.notify(
                title='Email Failed',
                message=f"{failed} of {sent + failed} email(s) failed to send in campaign '{campaign.name}'.",
                level='warning',
                link_url=f'/dashboard/campaigns/{campaign.pk}/',
            )

        return {'sent': sent, 'failed': failed}

    @staticmethod
    def record_open(open_token) -> bool:
        updated = CampaignRecipient.objects.filter(
            open_token=open_token, status=RecipientStatus.SENT,
        ).update(status=RecipientStatus.OPENED, opened_at=timezone.now())
        return updated > 0
