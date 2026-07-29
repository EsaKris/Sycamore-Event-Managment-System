"""
The public, unauthenticated registration flow. Deliberately kept in its
own module (not mixed into views.py, which is entirely login-required)
so there's never any ambiguity about which views in this app require a
session and which don't — every view in this file is public by design,
every view in views.py is not.
"""

import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.captcha import verify_hcaptcha
from apps.core.models import SystemSettings
from apps.events.models import Event, RegistrationStatus
from apps.people.services import DuplicatePersonError, PersonService

from . import idcards
from .models import Registration
from .public_forms import PublicRegistrationForm, WorkerPublicRegistrationForm
from .services import AlreadyRegisteredError, RegistrationService

logger = logging.getLogger(__name__)

RATE_LIMIT_MAX_SUBMISSIONS = 5
RATE_LIMIT_WINDOW_SECONDS = 3600

# Tighter than the submission throttle on purpose — this endpoint is a
# lookup, not a one-shot form post, so it's the more attractive target for
# someone trying to enumerate phone numbers and see whose name comes back.
LOOKUP_RATE_LIMIT_MAX = 8
LOOKUP_RATE_LIMIT_WINDOW_SECONDS = 3600

# Fields it's safe to hand back to "you, having just typed in your own
# phone number" so the rest of the form can be pre-filled. Deliberately
# excludes anything a stranger could misuse if this were ever probed —
# no medical/emergency-contact data, no full profile, just what the public
# form itself already asks for.
RETURNING_PERSON_FIELDS = (
    'first_name', 'last_name', 'gender', 'email_address', 'date_of_birth',
    'marital_status', 'state', 'country', 'church_name', 'occupation',
)


def _client_ip(request) -> str:
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    return forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR', 'unknown')


def _rate_limited(request, *, key_prefix='public_reg_throttle', max_count=RATE_LIMIT_MAX_SUBMISSIONS,
                   window_seconds=RATE_LIMIT_WINDOW_SECONDS) -> bool:
    """
    Basic per-IP throttle using Django's cache framework — intentionally
    simple (no captcha, no external service) rather than reaching for a
    third-party anti-spam dependency for what's still a low-traffic,
    single-conference registration form. Note: with the default LocMemCache
    this limit is per-process, not global across multiple workers/servers;
    swap in Redis/Memcached in CACHES for a real multi-worker deployment.
    """
    key = f'{key_prefix}:{_client_ip(request)}'
    count = cache.get(key, 0)
    if count >= max_count:
        return True
    cache.set(key, count + 1, window_seconds)
    return False


def _process_registration(request, event, settings_obj):
    """
    Shared core of the registration flow — used by both the slugged route
    (/register/<slug>/, for a specific/non-default event) and the short
    route (/register/, resolved via SystemSettings.default_event). Both
    end up on the same slugged confirmation URL (/register/<slug>/success/)
    on success, since a registration number in a URL wants a stable,
    unambiguous event context even when the entry point didn't need one.
    """
    if event.registration_status != RegistrationStatus.OPEN:
        return render(request, 'public/closed.html', {'event': event, 'settings': settings_obj})

    ctx = {'event': event, 'settings': settings_obj, 'hcaptcha_site_key': settings.HCAPTCHA_SITE_KEY}

    if request.method == 'POST':
        if _rate_limited(request):
            ctx.update(form=PublicRegistrationForm(), rate_limited=True)
            return render(request, 'public/register.html', ctx)

        form = PublicRegistrationForm(request.POST, request.FILES)
        if not verify_hcaptcha(request.POST.get('h-captcha-response', ''), remote_ip=_client_ip(request)):
            form.add_error(None, "We couldn't verify you're human — please try the checkbox again.")
        elif form.is_valid():
            try:
                result = RegistrationService.register_public(
                    event=event,
                    person_fields=form.person_fields(),
                    accommodation_requested=form.cleaned_data['accommodation_requested'],
                )
            except AlreadyRegisteredError:
                form.add_error(None, "Looks like you're already registered for this event. "
                                      "Check your phone or email for your registration details.")
            except DuplicatePersonError:
                # Only reachable in a race between two near-simultaneous submissions
                # with the same phone/email — register_public's search already
                # handles the normal case, so this is a last-resort safety net.
                form.add_error(None, "Something matched an existing record — please try again in a moment.")
            else:
                request.session['public_registration'] = {
                    'registration_id': result.registration.id,
                    'person_id': result.person.person_id,
                    'full_name': result.person.full_name,
                    'registration_number': result.registration.registration_number,
                    'event_title': event.title,
                    'event_slug': event.slug,
                    'category': 'participant',
                }
                return redirect('public:success', event_slug=event.slug)
    else:
        form = PublicRegistrationForm()

    ctx['form'] = form
    return render(request, 'public/register.html', ctx)


def _process_worker_registration(request, event, settings_obj):
    """
    Worker/Pastor counterpart of _process_registration — same shape, own
    form (WorkerPublicRegistrationForm) and its own throttle key so a
    burst of worker sign-ups can't eat into the participant form's rate
    limit (or vice versa) on a shared kiosk/IP.
    """
    if event.registration_status != RegistrationStatus.OPEN:
        return render(request, 'public/closed.html', {'event': event, 'settings': settings_obj})

    ctx = {'event': event, 'settings': settings_obj, 'hcaptcha_site_key': settings.HCAPTCHA_SITE_KEY}

    if request.method == 'POST':
        if _rate_limited(request, key_prefix='public_worker_reg_throttle'):
            ctx.update(form=WorkerPublicRegistrationForm(), rate_limited=True)
            return render(request, 'public/register_worker.html', ctx)

        form = WorkerPublicRegistrationForm(request.POST, request.FILES)
        if not verify_hcaptcha(request.POST.get('h-captcha-response', ''), remote_ip=_client_ip(request)):
            form.add_error(None, "We couldn't verify you're human — please try the checkbox again.")
        elif form.is_valid():
            try:
                result = RegistrationService.register_public_worker(
                    event=event,
                    person_fields=form.person_fields(),
                    registration_fields=form.registration_fields(),
                )
            except AlreadyRegisteredError:
                form.add_error(None, "Looks like you're already registered for this event. "
                                      "Check your phone or email for your registration details.")
            except DuplicatePersonError:
                # Only reachable in a race between two near-simultaneous submissions
                # with the same phone/email — register_public_worker's search already
                # handles the normal case, so this is a last-resort safety net.
                form.add_error(None, "Something matched an existing record — please try again in a moment.")
            else:
                request.session['public_registration'] = {
                    'registration_id': result.registration.id,
                    'person_id': result.person.person_id,
                    'full_name': result.person.full_name,
                    'registration_number': result.registration.registration_number,
                    'event_title': event.title,
                    'event_slug': event.slug,
                    'category': 'worker',
                    'worker_type': result.registration.get_worker_type_display(),
                    'department': result.registration.department.name if result.registration.department else '',
                }
                return redirect('public:success', event_slug=event.slug)
    else:
        form = WorkerPublicRegistrationForm()

    ctx['form'] = form
    return render(request, 'public/register_worker.html', ctx)


def public_register(request, event_slug):
    """Registration at its full, slugged URL — for events other than the
    current default, or for links shared directly to a specific event."""
    event = get_object_or_404(Event, slug=event_slug)
    return _process_registration(request, event, SystemSettings.load())


def public_register_default(request):
    """Registration at the short '/register/' URL — resolves whichever
    event is set as SystemSettings.default_event. This is what makes
    'sycamore.againandafresh.org/register' possible without a slug in it;
    if nothing's configured as default, there's simply nothing to
    register for yet at that URL."""
    settings_obj = SystemSettings.load()
    event = settings_obj.default_event
    if event is None:
        return render(request, 'public/no_active_event.html', {'settings': settings_obj})
    return _process_registration(request, event, settings_obj)


def public_register_worker(request, event_slug):
    """Worker/Pastor registration at its full, slugged URL."""
    event = get_object_or_404(Event, slug=event_slug)
    return _process_worker_registration(request, event, SystemSettings.load())


def public_register_worker_default(request):
    """Worker/Pastor registration at the short '/register/worker/' URL —
    resolves the same SystemSettings.default_event as the participant
    short route."""
    settings_obj = SystemSettings.load()
    event = settings_obj.default_event
    if event is None:
        return render(request, 'public/no_active_event.html', {'settings': settings_obj})
    return _process_worker_registration(request, event, settings_obj)


def public_register_success(request, event_slug):
    event = get_object_or_404(Event, slug=event_slug)
    data = request.session.get('public_registration')

    if not data or data.get('event_slug') != event_slug:
        return redirect('public:register', event_slug=event_slug)

    return render(request, 'public/success.html', {
        'event': event, 'data': data, 'settings': SystemSettings.load(),
    })


def _get_registration_by_token(event_slug, qr_token):
    """
    Shared lookup for the public card view/download endpoints. Gated by
    knowledge of the Person's qr_token — a random UUID that's already the
    secret encoded in the QR code printed on the card itself and used for
    attendance check-in — rather than a database primary key, so this is
    a capability URL (unguessable, not enumerable) and not a public
    listing: nobody can browse or iterate their way to someone else's card.
    """
    return get_object_or_404(
        Registration.objects.select_related('person', 'event', 'department'),
        person__qr_token=qr_token, event__slug=event_slug,
    )


def public_card_view(request, event_slug, qr_token):
    """The page linked from the registration confirmation email — shows
    the card and offers a PDF download, with no login required."""
    registration = _get_registration_by_token(event_slug, qr_token)
    return render(request, 'public/card.html', {
        'registration': registration, 'person': registration.person, 'event': registration.event,
    })


def public_card_png(request, event_slug, qr_token):
    """Inline PNG preview for public/card.html — never a download."""
    registration = _get_registration_by_token(event_slug, qr_token)
    return HttpResponse(idcards.render_card_png(registration), content_type='image/png')


def public_card_download(request, event_slug, qr_token):
    registration = _get_registration_by_token(event_slug, qr_token)
    pdf_bytes = idcards.render_card_pdf(registration)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{registration.person.person_id}-id-card.pdf"'
    return response


@require_POST
def check_returning(request):
    """
    Backs the "Have you attended before?" step on the public form. Matches
    only against the exact phone number the visitor themselves just typed
    into this same request — never a browsable search, never a list — so
    the privacy guarantee is the same as the invisible server-side match
    RegistrationService.register_public() already does on submit; this just
    surfaces it as a visible, deliberate step and pre-fills the form when
    it hits, instead of silently discovering the match only after submit.

    Rate-limited more tightly than the submission endpoint itself, since a
    "does this number exist" oracle is the more attractive thing to probe.
    """
    if _rate_limited(request, key_prefix='public_reg_lookup_throttle',
                      max_count=LOOKUP_RATE_LIMIT_MAX, window_seconds=LOOKUP_RATE_LIMIT_WINDOW_SECONDS):
        return JsonResponse({'matched': False, 'throttled': True}, status=429)

    try:
        payload = json.loads(request.body or b'{}')
    except (ValueError, TypeError):
        payload = request.POST

    phone_number = (payload.get('phone_number') or '').strip()
    if not phone_number:
        return JsonResponse({'matched': False}, status=400)

    match = PersonService.search(phone_number=phone_number)
    if not match:
        return JsonResponse({'matched': False})

    person = match.person
    data = {field: (getattr(person, field, '') or '') for field in RETURNING_PERSON_FIELDS}
    if hasattr(data.get('date_of_birth'), 'isoformat'):
        data['date_of_birth'] = data['date_of_birth'].isoformat()
    return JsonResponse({'matched': True, **data})


def landing(request):
    """The public marketing/landing page — hero, event details, FAQs, and
    a CTA into registration. Resolves the same default_event as the short
    '/register/' URL so there's one place (Settings) that controls which
    event is 'live' on the public site."""
    settings_obj = SystemSettings.load()
    event = settings_obj.default_event
    return render(request, 'public/landing.html', {'event': event, 'settings': settings_obj})
