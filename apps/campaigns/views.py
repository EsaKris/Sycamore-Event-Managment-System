"""
Email Campaigns UI.

    /dashboard/campaigns/templates/            -> reusable subject/body templates
    /dashboard/campaigns/templates/new/         -> create a template
    /dashboard/campaigns/templates/<id>/edit/   -> edit a template
    /dashboard/campaigns/                       -> campaign list
    /dashboard/campaigns/new/                   -> build a campaign (pick template + segment)
    /dashboard/campaigns/<id>/                  -> campaign detail: segment size, recipients, send
    /dashboard/campaigns/<id>/edit/             -> edit a still-draft campaign's segment
    /dashboard/campaigns/<id>/sync/             -> recalculate the recipient list
    /dashboard/campaigns/<id>/send/             -> send now
    /dashboard/campaigns/track/<uuid>.gif       -> open-tracking pixel (public, no login)
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView

from apps.core.models import AuditLog

from .forms import EmailCampaignForm, EmailTemplateForm, PLACEHOLDER_LEGEND
from .models import CampaignStatus, EmailCampaign, EmailTemplate, RecipientStatus
from .services import CampaignService

# 1x1 transparent GIF, served by the open-tracking pixel endpoint.
_TRACKING_PIXEL = bytes.fromhex(
    '47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b'
)


def _log(request, action, obj):
    AuditLog.objects.create(
        administrator=request.user if request.user.is_authenticated else None,
        action=action,
        model_name=obj.__class__.__name__,
        object_id=str(obj.pk),
        ip_address=getattr(request, 'client_ip', None) or request.META.get('REMOTE_ADDR'),
    )


# ---------------------------------------------------------------- Templates

class TemplateListView(LoginRequiredMixin, ListView):
    login_url = 'dashboard:login'
    model = EmailTemplate
    template_name = 'campaigns/template_list.html'
    context_object_name = 'templates'
    paginate_by = 25

    def get_queryset(self):
        return EmailTemplate.objects.order_by('-created_at')


@login_required(login_url='dashboard:login')
def template_form(request, pk=None):
    instance = get_object_or_404(EmailTemplate, pk=pk) if pk else None

    if request.method == 'POST':
        form = EmailTemplateForm(request.POST, instance=instance)
        if form.is_valid():
            template = form.save(commit=False)
            if not pk:
                template.created_by = request.user if request.user.is_authenticated else None
            template.save()
            _log(request, 'Created Email Template' if not pk else 'Updated Email Template', template)
            messages.success(request, f"Template '{template.name}' saved.")
            return redirect('campaigns:templates')
    else:
        form = EmailTemplateForm(instance=instance)

    return render(request, 'campaigns/template_form.html', {
        'form': form, 'instance': instance, 'placeholders': PLACEHOLDER_LEGEND,
    })


# ---------------------------------------------------------------- Campaigns

class CampaignListView(LoginRequiredMixin, ListView):
    login_url = 'dashboard:login'
    model = EmailCampaign
    template_name = 'campaigns/list.html'
    context_object_name = 'campaigns'
    paginate_by = 25

    def get_queryset(self):
        return (
            EmailCampaign.objects.select_related('template', 'event')
            .annotate(recipient_count=Count('recipients'))
            .order_by('-created_at')
        )


@login_required(login_url='dashboard:login')
def campaign_form(request, pk=None):
    instance = get_object_or_404(EmailCampaign, pk=pk) if pk else None
    if instance and instance.is_locked:
        messages.error(request, "This campaign has already started sending and can't be edited.")
        return redirect('campaigns:detail', pk=instance.pk)

    if not EmailTemplate.objects.filter(is_active=True).exists():
        messages.warning(request, 'Create an email template first — a campaign needs one to send.')
        return redirect('campaigns:template_create')

    if request.method == 'POST':
        form = EmailCampaignForm(request.POST, instance=instance)
        if form.is_valid():
            campaign = form.save(commit=False)
            if not pk:
                campaign.created_by = request.user if request.user.is_authenticated else None
            campaign.status = CampaignStatus.SCHEDULED if campaign.scheduled_at else CampaignStatus.DRAFT
            campaign.save()
            recipient_count = CampaignService.sync_recipients(campaign)
            _log(request, 'Created Email Campaign' if not pk else 'Updated Email Campaign', campaign)
            messages.success(request, f"Campaign '{campaign.name}' saved — {recipient_count} recipient{'s' if recipient_count != 1 else ''} matched.")
            return redirect('campaigns:detail', pk=campaign.pk)
    else:
        form = EmailCampaignForm(instance=instance)

    preview_count = None
    if instance:
        preview_count = CampaignService.build_segment(instance).values('person_id').distinct().count()

    return render(request, 'campaigns/campaign_form.html', {
        'form': form, 'instance': instance, 'preview_count': preview_count,
    })


@login_required(login_url='dashboard:login')
def campaign_detail(request, pk):
    campaign = get_object_or_404(EmailCampaign.objects.select_related('template', 'event', 'target_department'), pk=pk)
    recipients = campaign.recipients.select_related('person').order_by('person__first_name')
    counts = {
        'total': recipients.count(),
        'sent': recipients.filter(status=RecipientStatus.SENT).count(),
        'opened': recipients.filter(status=RecipientStatus.OPENED).count(),
        'failed': recipients.filter(status=RecipientStatus.FAILED).count(),
        'pending': recipients.filter(status=RecipientStatus.PENDING).count(),
    }
    return render(request, 'campaigns/detail.html', {
        'campaign': campaign, 'recipients': recipients[:200], 'counts': counts,
    })


@login_required(login_url='dashboard:login')
def campaign_sync(request, pk):
    campaign = get_object_or_404(EmailCampaign, pk=pk)
    if request.method == 'POST':
        count = CampaignService.sync_recipients(campaign)
        messages.success(request, f"Recipient list refreshed — {count} match this segment now.")
    return redirect('campaigns:detail', pk=campaign.pk)


@login_required(login_url='dashboard:login')
def campaign_send(request, pk):
    campaign = get_object_or_404(EmailCampaign, pk=pk)
    if request.method == 'POST':
        if campaign.is_locked:
            messages.error(request, 'This campaign has already been sent.')
        else:
            result = CampaignService.send_campaign(campaign, request=request)
            _log(request, 'Sent Email Campaign', campaign)
            messages.success(
                request,
                f"Campaign sent — {result['sent']} delivered"
                + (f", {result['failed']} failed" if result['failed'] else '') + '.',
            )
    return redirect('campaigns:detail', pk=campaign.pk)


def track_open(request, token):
    """Public open-tracking pixel — deliberately has no @login_required,
    it's loaded by the recipient's email client, not an administrator."""
    CampaignService.record_open(token)
    return HttpResponse(_TRACKING_PIXEL, content_type='image/gif')
