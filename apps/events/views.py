from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from apps.core.models import AuditLog

from .forms import EventForm
from .models import Event, EventStatus, RegistrationStatus
from .services import EventService


class EventListView(LoginRequiredMixin, ListView):
    login_url = 'dashboard:login'
    model = Event
    template_name = 'events/list.html'
    context_object_name = 'events'

    def get_queryset(self):
        qs = Event.objects.order_by('-year', '-start_date')
        status = self.request.GET.get('status', '')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['statuses'] = EventStatus.choices
        ctx['selected_status'] = self.request.GET.get('status', '')
        return ctx


class EventDetailView(LoginRequiredMixin, DetailView):
    login_url = 'dashboard:login'
    model = Event
    template_name = 'events/detail.html'
    context_object_name = 'event'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        event = self.object
        registrations = event.registrations.select_related('person', 'department')
        ctx['total_registrations'] = registrations.count()
        ctx['workers'] = registrations.filter(category='worker').count()
        ctx['participants'] = registrations.filter(category='participant').count()
        ctx['capacity_pct'] = (
            round(min(ctx['total_registrations'] / event.max_capacity, 1.0) * 100)
            if event.max_capacity else None
        )
        ctx['sessions_count'] = event.attendance_sessions.count()
        ctx['recent_registrations'] = registrations.order_by('-created_at')[:8]
        return ctx


@login_required(login_url='dashboard:login')
def event_form(request, pk=None):
    event = get_object_or_404(Event, pk=pk) if pk else None
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            is_new = event is None
            event = form.save()
            AuditLog.objects.create(
                administrator=request.user,
                action=f"{'Created' if is_new else 'Updated'} event '{event.title}'",
                model_name='Event', object_id=event.id,
                ip_address=getattr(request, 'client_ip', None),
            )
            messages.success(request, f"'{event.title}' saved.")
            return redirect('events:detail', pk=event.pk)
    else:
        form = EventForm(instance=event)
    return render(request, 'events/form.html', {'form': form, 'event': event})


@login_required(login_url='dashboard:login')
@require_POST
def event_toggle_registration(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if event.registration_status == RegistrationStatus.OPEN:
        EventService.close_registration(event, requested_by=request.user)
        messages.success(request, f"Registration closed for '{event.title}'.")
    else:
        EventService.open_registration(event, requested_by=request.user)
        messages.success(request, f"Registration opened for '{event.title}'.")
    return redirect('events:detail', pk=pk)


@login_required(login_url='dashboard:login')
@require_POST
def event_set_status(request, pk):
    event = get_object_or_404(Event, pk=pk)
    status = request.POST.get('status', '')
    if status in EventStatus.values:
        EventService.set_status(event, status, requested_by=request.user)
        messages.success(request, f"'{event.title}' is now {event.get_status_display()}.")
    return redirect('events:detail', pk=pk)
