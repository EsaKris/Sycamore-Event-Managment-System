"""
Registration flow UI.

A short session-backed wizard implementing the spec's exact flow:

    Have you attended any previous Sycamore Conference?
        NO  -> create Person -> create Registration
        YES -> search by phone/email/Person ID/QR -> load + allow editing
               -> update Person -> create Registration

State kept in request.session['reg_wizard'] is intentionally minimal
(event id, the yes/no answer, and — once matched — the returning
person's id) so there's nothing sensitive or bulky to serialize; the
actual Person/Registration data lives in ordinary bound forms on the
details step and is only written to the database once, inside
RegistrationService, when that step is submitted.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, ListView

from apps.core.models import AuditLog
from apps.events.models import Event
from apps.people.models import Person
from apps.people.services import DuplicatePersonError

from .forms import PersonForm, PersonSearchForm, RegistrationDetailsForm, StartForm
from .models import Registration, RegistrationStatus
from .services import AlreadyRegisteredError, RegistrationService

SESSION_KEY = 'reg_wizard'


def _wizard(request) -> dict:
    return request.session.get(SESSION_KEY, {})


def _save_wizard(request, **updates):
    state = _wizard(request)
    state.update(updates)
    request.session[SESSION_KEY] = state
    return state


def _clear_wizard(request):
    request.session.pop(SESSION_KEY, None)


def _log(request, action, obj):
    AuditLog.objects.create(
        administrator=request.user if request.user.is_authenticated else None,
        action=action,
        model_name=obj.__class__.__name__,
        object_id=str(obj.pk),
        ip_address=getattr(request, 'client_ip', None) or request.META.get('REMOTE_ADDR'),
    )


@login_required(login_url='dashboard:login')
def start(request):
    """Step 1 — choose the event and answer 'have you attended before?'."""
    _clear_wizard(request)

    if request.method == 'POST':
        form = StartForm(request.POST)
        if form.is_valid():
            event = form.cleaned_data['event']
            attended_before = form.cleaned_data['attended_before']
            _save_wizard(request, event_id=event.id, attended_before=attended_before)
            if attended_before == 'yes':
                return redirect('registrations:search')
            return redirect('registrations:details')
    else:
        form = StartForm()

    return render(request, 'registrations/start.html', {'form': form, 'step': 1})


@login_required(login_url='dashboard:login')
def search(request):
    """Step 2 (returning-attendee branch) — find the existing Person."""
    state = _wizard(request)
    if 'event_id' not in state or state.get('attended_before') != 'yes':
        return redirect('registrations:start')

    event = get_object_or_404(Event, pk=state['event_id'])
    result = None
    searched = False

    if request.method == 'POST':
        form = PersonSearchForm(request.POST)
        if form.is_valid():
            searched = True
            result = RegistrationService.find_returning_person(
                phone_number=form.cleaned_data['phone_number'],
                email_address=form.cleaned_data['email_address'],
                person_id=form.cleaned_data['person_id'],
                qr_token=form.cleaned_data['qr_token'],
            )
            if result:
                if Registration.objects.filter(person=result, event=event).exists():
                    messages.warning(
                        request,
                        f"{result.full_name} ({result.person_id}) is already registered for {event.title}.",
                    )
                    result = None
                else:
                    _save_wizard(request, person_id=result.id)
    else:
        form = PersonSearchForm()

    return render(request, 'registrations/search.html', {
        'form': form, 'event': event, 'result': result, 'searched': searched, 'step': 2,
    })


@login_required(login_url='dashboard:login')
def use_match(request):
    """Confirms the matched person from the search step and moves on."""
    state = _wizard(request)
    if not state.get('person_id'):
        return redirect('registrations:search')
    return redirect('registrations:details')


@login_required(login_url='dashboard:login')
def register_as_new(request):
    """Escape hatch from the search step: no match found, proceed as a first-timer."""
    state = _wizard(request)
    if 'event_id' not in state:
        return redirect('registrations:start')
    _save_wizard(request, attended_before='no', person_id=None)
    return redirect('registrations:details')


@login_required(login_url='dashboard:login')
def details(request):
    """Step 3 — Person details + this event's registration details, one page."""
    state = _wizard(request)
    if 'event_id' not in state:
        return redirect('registrations:start')

    event = get_object_or_404(Event, pk=state['event_id'])
    is_returning = state.get('attended_before') == 'yes'
    existing_person = None
    if is_returning:
        if not state.get('person_id'):
            return redirect('registrations:search')
        existing_person = get_object_or_404(Person, pk=state['person_id'])

    if request.method == 'POST':
        person_form = PersonForm(request.POST, request.FILES, instance=existing_person)
        reg_form = RegistrationDetailsForm(request.POST)

        if person_form.is_valid() and reg_form.is_valid():
            registration_fields = {
                'category': reg_form.cleaned_data['category'],
                'worker_type': reg_form.cleaned_data.get('worker_type') or '',
                'department': reg_form.cleaned_data.get('department'),
                'accommodation_requested': reg_form.cleaned_data['accommodation_requested'],
            }
            try:
                if is_returning:
                    result = RegistrationService.register_returning_person(
                        event=event,
                        person=existing_person,
                        updated_fields=person_form.cleaned_data,
                        registration_fields=registration_fields,
                    )
                    _log(request, 'Updated Person (via registration)', result.person)
                else:
                    result = RegistrationService.register_new_person(
                        event=event,
                        person_fields=person_form.cleaned_data,
                        registration_fields=registration_fields,
                    )
                    _log(request, 'Created Person', result.person)

                _log(request, 'Created Registration', result.registration)
                _clear_wizard(request)
                messages.success(
                    request,
                    f"{result.person.full_name} was registered for {event.title} "
                    f"({result.registration.registration_number}).",
                )
                return redirect('registrations:success', pk=result.registration.pk)

            except DuplicatePersonError as exc:
                messages.error(request, str(exc))
            except AlreadyRegisteredError as exc:
                messages.error(request, str(exc))
    else:
        person_form = PersonForm(instance=existing_person)
        reg_form = RegistrationDetailsForm()

    return render(request, 'registrations/details.html', {
        'person_form': person_form,
        'reg_form': reg_form,
        'event': event,
        'existing_person': existing_person,
        'is_returning': is_returning,
        'skip_search': not is_returning,
        'step': 3,
    })


@login_required(login_url='dashboard:login')
def success(request, pk):
    registration = get_object_or_404(
        Registration.objects.select_related('person', 'event', 'department'), pk=pk,
    )
    return render(request, 'registrations/success.html', {'registration': registration, 'step': 4})


class RegistrationListView(LoginRequiredMixin, ListView):
    login_url = 'dashboard:login'
    model = Registration
    template_name = 'registrations/list.html'
    context_object_name = 'registrations'
    paginate_by = 20

    def get_queryset(self):
        qs = Registration.objects.select_related('person', 'event', 'department').order_by('-created_at')
        q = self.request.GET.get('q', '').strip()
        event_id = self.request.GET.get('event', '')
        category = self.request.GET.get('category', '')
        status = self.request.GET.get('status', '')

        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(registration_number__icontains=q)
                | Q(person__first_name__icontains=q)
                | Q(person__last_name__icontains=q)
                | Q(person__phone_number__icontains=q)
                | Q(person__person_id__icontains=q)
            )
        if event_id:
            qs = qs.filter(event_id=event_id)
        if category:
            qs = qs.filter(category=category)
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            'events': Event.objects.order_by('-year'),
            'statuses': RegistrationStatus.choices,
            'q': self.request.GET.get('q', ''),
            'selected_event': self.request.GET.get('event', ''),
            'selected_category': self.request.GET.get('category', ''),
            'selected_status': self.request.GET.get('status', ''),
            'total_count': self.get_queryset().count(),
        })
        return ctx


class RegistrationDetailView(LoginRequiredMixin, DetailView):
    login_url = 'dashboard:login'
    model = Registration
    template_name = 'registrations/detail.html'
    context_object_name = 'registration'

    def get_queryset(self):
        return Registration.objects.select_related('person', 'event', 'department')


# --------------------------------------------------------------------------
# ID Card generation
# --------------------------------------------------------------------------
from . import idcards  # noqa: E402  (grouped separately — only this section needs it)


@login_required(login_url='dashboard:login')
def id_card_preview(request, pk):
    """Inline PNG preview — used as an <img src> on the detail page and
    the bulk-print picker, never as a download."""
    registration = get_object_or_404(Registration.objects.select_related('person', 'event', 'department'), pk=pk)
    return HttpResponse(idcards.render_card_png(registration), content_type='image/png')


@login_required(login_url='dashboard:login')
def id_card_download(request, pk):
    registration = get_object_or_404(Registration.objects.select_related('person', 'event', 'department'), pk=pk)
    pdf_bytes = idcards.render_card_pdf(registration)
    AuditLog.objects.create(
        administrator=request.user,
        action=f"Downloaded ID card for {registration.person.full_name} ({registration.person.person_id})",
        model_name='Registration', object_id=registration.id,
        ip_address=getattr(request, 'client_ip', None),
    )
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{registration.person.person_id}-id-card.pdf"'
    return response


@login_required(login_url='dashboard:login')
def id_card_picker(request):
    """Event picker + checklist of registrations to bulk-print, per spec's
    'Bulk Print' requirement. Mirrors the event-first pattern already used
    by the attendance scanner."""
    event_id = request.GET.get('event')
    event = Event.objects.filter(pk=event_id).first() if event_id else None

    registrations = []
    if event:
        registrations = (
            Registration.objects.filter(event=event)
            .select_related('person', 'department').order_by('person__last_name', 'person__first_name')
        )

    return render(request, 'registrations/id_cards.html', {
        'events': Event.objects.order_by('-year'),
        'event': event,
        'registrations': registrations,
    })


@login_required(login_url='dashboard:login')
def id_card_bulk_download(request):
    """Accepts either specific registration ids (checkbox selection) or
    an event id (print everyone) and streams back one multi-page PDF."""
    ids = request.POST.getlist('registration_ids') or request.GET.getlist('registration_ids')
    event_id = request.POST.get('event') or request.GET.get('event')

    if ids:
        registrations = Registration.objects.filter(pk__in=ids).select_related('person', 'event', 'department')
    elif event_id:
        registrations = Registration.objects.filter(event_id=event_id).select_related('person', 'event', 'department')
    else:
        messages.error(request, 'Select at least one registration to print.')
        return redirect('registrations:id_cards')

    if not registrations.exists():
        messages.error(request, 'No matching registrations found to print.')
        return redirect('registrations:id_cards')

    pdf_bytes = idcards.render_cards_pdf(list(registrations))
    AuditLog.objects.create(
        administrator=request.user,
        action=f"Bulk-downloaded {registrations.count()} ID card(s)",
        model_name='Registration', object_id='',
        ip_address=getattr(request, 'client_ip', None),
    )
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="sems-id-cards.pdf"'
    return response


@login_required(login_url='dashboard:login')
def id_card_set_badge_label(request, pk):
    """Small inline control on the detail page for the VIP/Speaker/
    Volunteer override mentioned in the spec's card-type list, without
    needing a full edit form."""
    registration = get_object_or_404(Registration, pk=pk)
    if request.method == 'POST':
        registration.badge_label = request.POST.get('badge_label', '').strip()
        registration.save(update_fields=['badge_label'])
        messages.success(request, 'Badge label updated.')
    return redirect('registrations:detail', pk=pk)
