from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.views.generic import TemplateView

from apps.accounts.mixins import SuperAdminRequiredMixin
from apps.core.models import AuditLog, Notification, SystemSettings
from apps.core.services import NotificationService
from apps.departments.models import Department
from apps.events.models import Event, EventStatus
from apps.people.models import Gender, Person
from apps.registrations.models import Registration, RegistrationCategory, WorkerType
from apps.attendance.models import Attendance, CheckType
from apps.followup.models import FollowUp, FollowUpStatus

from .forms import AdminLoginForm
from .search import global_search
from . import reports as reports_module
from . import exports as exports_module
from .analytics import build_analytics


class AdminLoginView(LoginView):
    template_name = 'dashboard/login.html'
    authentication_form = AdminLoginForm
    redirect_authenticated_user = True


class AdminLogoutView(LogoutView):
    next_page = 'dashboard:login'


class DashboardHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/home.html'
    login_url = 'dashboard:login'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()

        # Scope "current" stats to the active/upcoming event if there is one,
        # otherwise fall back to system-wide totals across all events.
        active_event = (
            Event.objects.filter(status__in=[EventStatus.ACTIVE, EventStatus.UPCOMING])
            .order_by('start_date').first()
        )
        registrations = Registration.objects.filter(event=active_event) if active_event else Registration.objects.all()

        total_registrations = registrations.count()
        today_registrations = registrations.filter(created_at__date=today).count()
        returning_attendees = registrations.filter(is_returning_attendee=True).count()
        first_time_visitors = registrations.filter(is_returning_attendee=False).count()
        workers = registrations.filter(category=RegistrationCategory.WORKER).count()
        participants = registrations.filter(category=RegistrationCategory.PARTICIPANT).count()
        pastors = registrations.filter(worker_type=WorkerType.PASTOR).count()
        accommodation_requests = registrations.filter(accommodation_requested=True).count()

        top_departments = (
            registrations.exclude(department__isnull=True)
            .values('department__name')
            .annotate(total=Count('id'))
            .order_by('-total')[:5]
        )

        gender_stats_qs = (
            Person.objects.filter(registrations__in=registrations)
            .values('gender').annotate(total=Count('id', distinct=True)).order_by('gender')
        )
        gender_labels = dict(Gender.choices)
        gender_stats = [
            {'label': gender_labels.get(g['gender'], g['gender'] or 'Unspecified'), 'total': g['total']}
            for g in gender_stats_qs
        ]

        state_distribution = (
            Person.objects.filter(registrations__in=registrations)
            .exclude(state='').values('state').annotate(total=Count('id', distinct=True))
            .order_by('-total')[:6]
        )

        # 7-day registration trend
        trend = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            trend.append({'date': day.strftime('%a'), 'count': registrations.filter(created_at__date=day).count()})
        max_trend = max((t['count'] for t in trend), default=0) or 1

        recent_registrations = registrations.select_related('person', 'event', 'department').order_by('-created_at')[:6]
        upcoming_events = Event.objects.filter(start_date__gte=today).order_by('start_date')[:4]
        recent_activity = AuditLog.objects.select_related('administrator').order_by('-created_at')[:6]

        registration_progress = None
        if active_event and active_event.max_capacity:
            registration_progress = round(min(total_registrations / active_event.max_capacity, 1.0) * 100)

        # ---- Attendance (Phase: Attendance + QR) ----
        event_attendance = Attendance.objects.filter(event=active_event) if active_event else Attendance.objects.none()
        today_check_ins = event_attendance.filter(check_type=CheckType.CHECK_IN, created_at__date=today).count()
        today_check_outs = event_attendance.filter(check_type=CheckType.CHECK_OUT, created_at__date=today).count()

        # "Currently in the building": checked in today but not yet checked out of that same session.
        checked_in_ids = set(
            event_attendance.filter(check_type=CheckType.CHECK_IN, created_at__date=today)
            .values_list('person_id', 'session_id')
        )
        checked_out_ids = set(
            event_attendance.filter(check_type=CheckType.CHECK_OUT, created_at__date=today)
            .values_list('person_id', 'session_id')
        )
        current_attendance = len(checked_in_ids - checked_out_ids)

        attendance_progress = None
        if active_event and total_registrations:
            unique_checked_in = event_attendance.filter(check_type=CheckType.CHECK_IN).values('person_id').distinct().count()
            attendance_progress = round(min(unique_checked_in / total_registrations, 1.0) * 100)

        recent_scans = (
            Attendance.objects.select_related('person', 'session', 'event')
            .order_by('-created_at')[:6]
        )

        # ---- Follow-up ----
        pending_followups = FollowUp.objects.filter(status=FollowUpStatus.OPEN).count()
        overdue_followups = FollowUp.objects.filter(
            status=FollowUpStatus.OPEN, next_follow_up_date__lt=today,
        ).count()

        ctx.update({
            'active_event': active_event,
            'total_registrations': total_registrations,
            'today_registrations': today_registrations,
            'returning_attendees': returning_attendees,
            'first_time_visitors': first_time_visitors,
            'workers': workers,
            'participants': participants,
            'pastors': pastors,
            'departments_count': Department.objects.filter(is_active=True).count(),
            'accommodation_requests': accommodation_requests,
            'registration_progress': registration_progress,
            'top_departments': list(top_departments),
            'gender_stats': gender_stats,
            'state_distribution': list(state_distribution),
            'trend': trend,
            'max_trend': max_trend,
            'recent_registrations': recent_registrations,
            'upcoming_events': upcoming_events,
            'recent_activity': recent_activity,
            'today_check_ins': today_check_ins,
            'today_check_outs': today_check_outs,
            'current_attendance': current_attendance,
            'attendance_progress': attendance_progress,
            'recent_scans': recent_scans,
            'pending_followups': pending_followups,
            'overdue_followups': overdue_followups,
        })
        return ctx


@login_required(login_url='dashboard:login')
def change_password(request):
    forced = request.user.must_reset_password
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            user.must_reset_password = False
            user.save(update_fields=['must_reset_password'])
            update_session_auth_hash(request, user)  # keep them logged in through the password change
            AuditLog.objects.create(administrator=user, action='Changed own password', model_name='User', object_id=str(user.id))
            messages.success(request, 'Password updated.')
            return redirect('dashboard:home')
    else:
        form = PasswordChangeForm(request.user)
    for field in form.fields.values():
        field.widget.attrs.update({'class': 'field-input'})
    return render(request, 'dashboard/change_password.html', {'form': form, 'forced': forced})


@login_required(login_url='dashboard:login')
def search_api(request):
    """Powers the topbar's live dropdown (fetch-as-you-type)."""
    query = request.GET.get('q', '')
    groups = global_search(query, user=request.user)
    return JsonResponse({
        'query': query,
        'groups': [
            {
                'label': g.label,
                'results': [
                    {'title': r.title, 'subtitle': r.subtitle, 'url': r.url, 'icon': r.icon}
                    for r in g.results
                ],
            }
            for g in groups
        ],
    })


@login_required(login_url='dashboard:login')
def search_page(request):
    """Full results page — reached by pressing Enter, or used directly
    when JavaScript is unavailable."""
    query = request.GET.get('q', '')
    groups = global_search(query, user=request.user)
    return render(request, 'dashboard/search.html', {'query': query, 'groups': groups})


@login_required(login_url='dashboard:login')
def reports_index(request):
    report_key = request.GET.get('report', 'registrations')
    event_id = request.GET.get('event', '')
    event = Event.objects.filter(pk=event_id).first() if event_id else None

    spec = reports_module.REPORT_TYPES.get(report_key)
    columns, rows = reports_module.get_report_rows(report_key, event=event)

    return render(request, 'dashboard/reports.html', {
        'report_types': reports_module.REPORT_TYPES,
        'selected_report': report_key,
        'selected_report_label': spec['label'] if spec else '',
        'event_scoped': spec['event_scoped'] if spec else False,
        'events': Event.objects.order_by('-year'),
        'selected_event': event,
        'columns': columns,
        'rows': rows[:100],  # preview only — full data goes through export
        'total_rows': len(rows),
        'export_formats': [('csv', 'CSV'), ('xlsx', 'Excel'), ('pdf', 'PDF')],
    })


@login_required(login_url='dashboard:login')
def report_export(request):
    report_key = request.GET.get('report', 'registrations')
    fmt = request.GET.get('format', 'csv')
    event_id = request.GET.get('event', '')
    event = Event.objects.filter(pk=event_id).first() if event_id else None

    spec = reports_module.REPORT_TYPES.get(report_key)
    if not spec or fmt not in exports_module.EXPORTERS:
        messages.error(request, 'Unknown report or export format.')
        return redirect('dashboard:reports')

    columns, rows = reports_module.get_report_rows(report_key, event=event)
    title = f"{spec['label']}{' - ' + event.title if event else ''}".replace(' ', '_')

    AuditLog.objects.create(
        administrator=request.user,
        action=f"Exported '{spec['label']}' report as {fmt.upper()} ({len(rows)} rows)",
        model_name='Report', object_id='',
        ip_address=getattr(request, 'client_ip', None),
    )
    return exports_module.EXPORTERS[fmt](title, columns, rows)


@login_required(login_url='dashboard:login')
def analytics_view(request):
    event_id = request.GET.get('event', '')
    event = Event.objects.filter(pk=event_id).first() if event_id else None
    data = build_analytics(event=event)

    return render(request, 'dashboard/analytics.html', {
        'events': Event.objects.order_by('-year'),
        'selected_event': event,
        'analytics': data,
    })


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------

@login_required(login_url='dashboard:login')
def notifications_dropdown_api(request):
    unread = NotificationService.unread_for(request.user, limit=8)
    return JsonResponse({
        'count': NotificationService.unread_count(request.user),
        'items': [
            {
                'id': n.id, 'title': n.title, 'message': n.message, 'level': n.level,
                'link_url': n.link_url, 'created_at': timesince_short(n.created_at),
            }
            for n in unread
        ],
    })


def timesince_short(dt):
    from django.utils.timesince import timesince
    return timesince(dt).split(',')[0] + ' ago'


@login_required(login_url='dashboard:login')
@require_POST
def notification_mark_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk)
    NotificationService.mark_read(notification, request.user)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({'ok': True})
    return redirect(notification.link_url or 'dashboard:notifications')


@login_required(login_url='dashboard:login')
@require_POST
def notification_mark_all_read(request):
    NotificationService.mark_all_read(request.user)
    return JsonResponse({'ok': True})


@login_required(login_url='dashboard:login')
def notifications_page(request):
    notifications = Notification.objects.all()[:100]
    read_ids = set(request.user.read_notifications.values_list('id', flat=True))
    return render(request, 'dashboard/notifications.html', {
        'notifications': notifications,
        'read_ids': read_ids,
    })


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------

class SettingsView(SuperAdminRequiredMixin, TemplateView):
    template_name = 'dashboard/settings.html'

    def get_context_data(self, **kwargs):
        from django.conf import settings as django_settings
        ctx = super().get_context_data(**kwargs)
        ctx['settings'] = SystemSettings.load()
        ctx['email_backend'] = django_settings.EMAIL_BACKEND
        ctx['default_from_email'] = django_settings.DEFAULT_FROM_EMAIL
        ctx['email_host'] = django_settings.EMAIL_HOST or '(not configured — using console backend)'
        ctx['person_id_prefix'] = django_settings.SEMS_PERSON_ID_PREFIX
        ctx['person_id_digits'] = django_settings.SEMS_PERSON_ID_DIGITS
        ctx['departments'] = Department.objects.order_by('name')
        ctx['public_events'] = Event.objects.exclude(status=EventStatus.ARCHIVED).order_by('-year')
        return ctx

    def post(self, request, *args, **kwargs):
        obj = SystemSettings.load()
        obj.system_name = request.POST.get('system_name', obj.system_name).strip() or obj.system_name
        obj.church_name = request.POST.get('church_name', obj.church_name).strip()
        obj.support_email = request.POST.get('support_email', '').strip()
        obj.default_color_theme = request.POST.get('default_color_theme', obj.default_color_theme).strip()
        obj.default_theme_mode = request.POST.get('default_theme_mode', obj.default_theme_mode)
        obj.giving_url = request.POST.get('giving_url', '').strip()
        default_event_id = request.POST.get('default_event', '').strip()
        obj.default_event_id = int(default_event_id) if default_event_id else None
        if request.FILES.get('church_logo'):
            obj.church_logo = request.FILES['church_logo']
        obj.save()

        AuditLog.objects.create(
            administrator=request.user, action='Updated system settings',
            model_name='SystemSettings', object_id='1',
            ip_address=getattr(request, 'client_ip', None),
        )
        messages.success(request, 'Settings updated.')
        return redirect('dashboard:settings')


@login_required(login_url='dashboard:login')
def activity_logs(request):
    logs = AuditLog.objects.select_related('administrator').order_by('-created_at')

    admin_id = request.GET.get('administrator', '')
    model_name = request.GET.get('model', '')
    q = request.GET.get('q', '').strip()

    if admin_id:
        logs = logs.filter(administrator_id=admin_id)
    if model_name:
        logs = logs.filter(model_name=model_name)
    if q:
        logs = logs.filter(action__icontains=q)

    from django.core.paginator import Paginator
    paginator = Paginator(logs, 40)
    page_obj = paginator.get_page(request.GET.get('page'))

    from apps.accounts.models import User
    return render(request, 'dashboard/activity_logs.html', {
        'page_obj': page_obj,
        'paginator': paginator,
        'administrators': User.objects.order_by('username'),
        'model_names': AuditLog.objects.exclude(model_name='').values_list('model_name', flat=True).distinct().order_by('model_name'),
        'selected_admin': admin_id,
        'selected_model': model_name,
        'query': q,
        'total_count': logs.count(),
    })
