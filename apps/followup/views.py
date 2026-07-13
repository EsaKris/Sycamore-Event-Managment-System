"""
Follow-up Management UI.

    /dashboard/followup/                    -> global list of timeline entries, filterable
    /dashboard/followup/find/                -> "Find a Person" lookup (phone/email/Person ID/QR)
    /dashboard/followup/person/<person_id>/  -> that Person's full timeline + add-entry form
    /dashboard/followup/<id>/close/          -> one-click close from the list/timeline
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import ListView

from apps.attendance.services import AttendanceService
from apps.core.models import AuditLog
from apps.events.models import Event
from apps.people.models import Person

from .forms import FollowUpForm, FollowUpQuickCloseForm, PersonLookupForm
from .models import FollowUp, FollowUpStatus
from .services import FollowUpService


def _log(request, action, obj):
    AuditLog.objects.create(
        administrator=request.user if request.user.is_authenticated else None,
        action=action,
        model_name=obj.__class__.__name__,
        object_id=str(obj.pk),
        ip_address=getattr(request, 'client_ip', None) or request.META.get('REMOTE_ADDR'),
    )


class FollowUpListView(LoginRequiredMixin, ListView):
    login_url = 'dashboard:login'
    model = FollowUp
    template_name = 'followup/list.html'
    context_object_name = 'entries'
    paginate_by = 25

    def get_queryset(self):
        qs = FollowUp.objects.select_related('person', 'event', 'officer_assigned').order_by('-created_at')
        q = self.request.GET.get('q', '').strip()
        status = self.request.GET.get('status', '')
        follow_up_type = self.request.GET.get('type', '')
        event_id = self.request.GET.get('event', '')

        if q:
            qs = qs.filter(
                Q(person__first_name__icontains=q) | Q(person__last_name__icontains=q)
                | Q(person__phone_number__icontains=q) | Q(person__person_id__icontains=q)
            )
        if status:
            qs = qs.filter(status=status)
        if follow_up_type:
            qs = qs.filter(follow_up_type=follow_up_type)
        if event_id:
            qs = qs.filter(event_id=event_id)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base_qs = FollowUp.objects.all()
        ctx.update({
            'events': Event.objects.order_by('-year'),
            'q': self.request.GET.get('q', ''),
            'selected_status': self.request.GET.get('status', ''),
            'selected_type': self.request.GET.get('type', ''),
            'selected_event': self.request.GET.get('event', ''),
            'total_count': self.get_queryset().count(),
            'open_count': base_qs.filter(status=FollowUpStatus.OPEN).count(),
            'overdue_count': base_qs.filter(
                status=FollowUpStatus.OPEN,
                next_follow_up_date__lt=timezone.localdate(),
            ).count(),
        })
        return ctx


@login_required(login_url='dashboard:login')
def find_person(request):
    """The 'Find a Person' entry point — same identifier types accepted
    everywhere else in the system (phone / email / Person ID / QR)."""
    result = None
    searched = False

    if request.method == 'POST':
        form = PersonLookupForm(request.POST)
        if form.is_valid():
            searched = True
            identifier = form.cleaned_data['identifier']
            result = AttendanceService.find_person(identifier)
            if not result and '@' in identifier:
                result = Person.objects.filter(email_address__iexact=identifier.strip()).first()
            if result:
                return redirect('followup:timeline', person_id=result.person_id)
    else:
        form = PersonLookupForm()

    return render(request, 'followup/find_person.html', {
        'form': form, 'result': result, 'searched': searched,
    })


@login_required(login_url='dashboard:login')
def timeline(request, person_id):
    person = get_object_or_404(Person, person_id=person_id)
    summary = FollowUpService.get_timeline(person)

    if request.method == 'POST':
        form = FollowUpForm(request.POST)
        if form.is_valid():
            entry = FollowUpService.create_entry(
                person=person,
                logged_by=request.user if request.user.is_authenticated else None,
                **form.cleaned_data,
            )
            _log(request, 'Created Follow-up', entry)
            messages.success(request, f"Follow-up logged for {person.full_name}.")
            return redirect('followup:timeline', person_id=person.person_id)
    else:
        form = FollowUpForm()

    return render(request, 'followup/timeline.html', {
        'person': person, 'summary': summary, 'form': form,
    })


@login_required(login_url='dashboard:login')
def close_entry(request, pk):
    entry = get_object_or_404(FollowUp, pk=pk)
    if request.method == 'POST':
        form = FollowUpQuickCloseForm(request.POST)
        if form.is_valid():
            entry.close(outcome=form.cleaned_data['outcome'])
            _log(request, 'Closed Follow-up', entry)
            messages.success(request, f"Follow-up for {entry.person.full_name} marked closed.")
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('followup:timeline', person_id=entry.person.person_id)
