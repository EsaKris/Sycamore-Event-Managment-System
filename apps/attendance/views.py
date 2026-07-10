import json

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from apps.core.models import AuditLog
from apps.events.models import Event

from .forms import EventPickerForm, SessionCreateForm
from .models import Attendance, AttendanceSession, CheckType
from .services import AttendanceService


def _log(request, action, model_name='', object_id=''):
    AuditLog.objects.create(
        administrator=request.user if request.user.is_authenticated else None,
        action=action, model_name=model_name, object_id=str(object_id),
        ip_address=getattr(request, 'client_ip', None),
    )


@login_required(login_url='dashboard:login')
def scanner_view(request):
    event_id = request.GET.get('event')
    session_id = request.GET.get('session')

    event = Event.objects.filter(pk=event_id).first() if event_id else None
    event_form = EventPickerForm(initial={'event': event.id} if event else None)

    sessions = AttendanceSession.objects.filter(event=event, is_active=True).order_by('-date') if event else []
    selected_session = None
    if event and session_id:
        selected_session = AttendanceSession.objects.filter(pk=session_id, event=event).first()

    session_form = SessionCreateForm(event=event) if event else None

    recent_scans = []
    checked_in_count = checked_out_count = 0
    if selected_session:
        recent_scans = (
            Attendance.objects.filter(session=selected_session)
            .select_related('person', 'scanned_by').order_by('-created_at')[:12]
        )
        checked_in_count = Attendance.objects.filter(session=selected_session, check_type=CheckType.CHECK_IN).count()
        checked_out_count = Attendance.objects.filter(session=selected_session, check_type=CheckType.CHECK_OUT).count()

    return render(request, 'attendance/scanner.html', {
        'event_form': event_form,
        'event': event,
        'sessions': sessions,
        'selected_session': selected_session,
        'session_form': session_form,
        'recent_scans': recent_scans,
        'checked_in_count': checked_in_count,
        'checked_out_count': checked_out_count,
        'today': timezone.localdate(),
    })


@login_required(login_url='dashboard:login')
@require_POST
def session_create(request):
    event = get_object_or_404(Event, pk=request.POST.get('event'))
    form = SessionCreateForm(request.POST, event=event)
    if form.is_valid():
        session = form.save()
        _log(request, f"Created attendance session '{session.label}'", 'AttendanceSession', session.id)
        return redirect(f"{reverse('attendance:scanner')}?event={event.id}&session={session.id}")

    # Fall back to re-rendering the scanner page with the form errors.
    sessions = AttendanceSession.objects.filter(event=event, is_active=True).order_by('-date')
    return render(request, 'attendance/scanner.html', {
        'event_form': EventPickerForm(initial={'event': event.id}),
        'event': event,
        'sessions': sessions,
        'selected_session': None,
        'session_form': form,
        'recent_scans': [],
        'checked_in_count': 0,
        'checked_out_count': 0,
        'today': timezone.localdate(),
    })


def _person_json(person, registration=None):
    return {
        'person_id': person.person_id,
        'full_name': person.full_name,
        'photo_url': person.photo.url if person.photo else None,
        'gender': person.get_gender_display() if person.gender else '',
        'category': registration.get_category_display() if registration else None,
        'worker_type': registration.get_worker_type_display() if registration and registration.worker_type else None,
        'department': registration.department.name if registration and registration.department else None,
        'registration_status': registration.get_status_display() if registration else None,
        'registration_number': registration.registration_number if registration else None,
    }


def _attendance_json(attendance):
    return {
        'id': attendance.id,
        'check_type': attendance.get_check_type_display(),
        'session_label': attendance.session.label,
        'scanned_at': timezone.localtime(attendance.created_at).strftime('%b %d, %I:%M %p'),
        'scanned_by': attendance.scanned_by.get_full_name() or attendance.scanned_by.username if attendance.scanned_by else 'System',
    }


@login_required(login_url='dashboard:login')
@require_POST
def scan_api(request):
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Malformed request.'}, status=400)

    code = (payload.get('code') or '').strip()
    check_type = payload.get('check_type')
    event = Event.objects.filter(pk=payload.get('event_id')).first()
    session = AttendanceSession.objects.filter(pk=payload.get('session_id')).first()

    if not code:
        return JsonResponse({'status': 'error', 'message': 'Enter or scan a code first.'}, status=400)
    if not event or not session or session.event_id != event.id:
        return JsonResponse({'status': 'error', 'message': 'Select an event and session first.'}, status=400)
    if check_type not in (CheckType.CHECK_IN, CheckType.CHECK_OUT):
        return JsonResponse({'status': 'error', 'message': 'Invalid check type.'}, status=400)

    outcome = AttendanceService.scan(
        code=code, event=event, session=session, check_type=check_type,
        scanner=request.user, location=request.META.get('REMOTE_ADDR', ''),
    )

    if outcome.ok:
        _log(
            request,
            f"{outcome.attendance.get_check_type_display()} — {outcome.person.full_name} ({outcome.person.person_id})",
            'Attendance', outcome.attendance.id,
        )

    return JsonResponse({
        'status': outcome.status.value,
        'ok': outcome.ok,
        'is_warning': outcome.is_warning,
        'message': outcome.message,
        'person': _person_json(outcome.person, outcome.registration) if outcome.person else None,
        'attendance': _attendance_json(outcome.attendance) if outcome.attendance else None,
        'recent_attendance': [_attendance_json(a) for a in outcome.recent_attendance],
    })


class AttendanceLogView(LoginRequiredMixin, ListView):
    template_name = 'attendance/log.html'
    context_object_name = 'records'
    paginate_by = 25
    login_url = 'dashboard:login'

    def get_queryset(self):
        qs = Attendance.objects.select_related('person', 'event', 'session', 'scanned_by').order_by('-created_at')
        params = self.request.GET
        if params.get('event'):
            qs = qs.filter(event_id=params['event'])
        if params.get('session'):
            qs = qs.filter(session_id=params['session'])
        if params.get('check_type'):
            qs = qs.filter(check_type=params['check_type'])
        q = params.get('q', '').strip()
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(person__first_name__icontains=q) | Q(person__last_name__icontains=q)
                | Q(person__person_id__icontains=q) | Q(person__phone_number__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['events'] = Event.objects.order_by('-year')
        ctx['sessions'] = AttendanceSession.objects.order_by('-date')
        ctx['selected_event'] = self.request.GET.get('event', '')
        ctx['selected_session'] = self.request.GET.get('session', '')
        ctx['selected_check_type'] = self.request.GET.get('check_type', '')
        ctx['query'] = self.request.GET.get('q', '')
        ctx['total_count'] = self.get_queryset().count()
        return ctx
