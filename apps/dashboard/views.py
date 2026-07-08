from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count
from django.utils import timezone
from django.views.generic import TemplateView

from apps.core.models import AuditLog
from apps.departments.models import Department
from apps.events.models import Event, EventStatus
from apps.people.models import Gender, Person
from apps.registrations.models import Registration, RegistrationCategory, WorkerType

from .forms import AdminLoginForm


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
        })
        return ctx
