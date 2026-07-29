"""
Registration confirmation email — sent once, right after a Registration
is created, from RegistrationService (register_new_person /
register_returning_person) so every path that creates a Registration
gets it: the public participant form, the public worker/pastor form, and
the staff dashboard wizard alike.

Deliberately plain text (matching apps/accounts/services.py's admin
credential email) rather than HTML — no template, no styling, just the
facts and one link. Failures never propagate: a broken SMTP config
should never turn into a failed registration for the person standing at
the front desk.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

logger = logging.getLogger(__name__)


def _card_url(registration, request=None) -> str:
    path = reverse('public:card', kwargs={
        'event_slug': registration.event.slug, 'qr_token': registration.person.qr_token,
    })
    if request is not None:
        return request.build_absolute_uri(path)
    base = (settings.SEMS_SITE_URL or '').rstrip('/')
    return f'{base}{path}' if base else path


def send_registration_confirmation_email(registration, *, request=None) -> bool:
    """
    Returns True if an email was attempted (address was present), False
    if there was no email address to send to. Never raises — a failure
    here is logged, not surfaced to the person registering.
    """
    person = registration.person
    if not person.email_address:
        return False

    event = registration.event
    card_url = _card_url(registration, request=request)

    lines = [
        f"Hi {person.first_name},",
        "",
        f"You're registered for {event.title}.",
        "",
        f"Registration number: {registration.registration_number}",
        f"Your permanent ID: {person.person_id}",
        f"Registered as: {registration.card_label}",
    ]
    if registration.department:
        lines.append(f"Department: {registration.department.name}")
    if event.start_date and event.end_date:
        lines.append(f"Dates: {event.start_date:%B %d} \u2013 {event.end_date:%B %d, %Y}")
    if event.venue:
        lines.append(f"Venue: {event.venue}")

    lines += [
        "",
        f"View and download your ID card here: {card_url}",
        "",
        "See you there!",
    ]

    try:
        send_mail(
            subject=f"You're registered for {event.title}",
            message='\n'.join(lines),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@sems.local'),
            recipient_list=[person.email_address],
            fail_silently=False,
        )
    except Exception:
        # A dead SMTP config or a bad address should never break a
        # registration that already succeeded in the database.
        logger.exception(
            'Failed to send registration confirmation email for %s (%s)',
            person.full_name, registration.registration_number,
        )
    return True
