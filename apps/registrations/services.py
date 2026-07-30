"""
Implements the registration flow from the spec:

    Have you attended any previous Sycamore Conference?
        NO  -> create Person, create Registration
        YES -> search (phone/email/person_id/qr) -> load + allow edits ->
               update Person -> create Registration for the selected event
"""

from dataclasses import dataclass
from typing import Optional

from django.db import transaction

from apps.core.models import AuditLog
from apps.core.services import NotificationService
from apps.people.models import Person
from apps.people.services import DuplicatePersonError, PersonService

from .emails import send_registration_confirmation_email
from .models import Registration


class AlreadyRegisteredError(Exception):
    """Raised when this Person already has a Registration for this Event."""


@dataclass
class RegistrationResult:
    person: Person
    registration: Registration
    person_was_created: bool


class RegistrationService:

    @staticmethod
    @transaction.atomic
    def register_new_person(
        *, event, person_fields: dict, registration_fields: dict, actor=None, ip_address: str = '',
    ) -> RegistrationResult:
        """
        'NO, I have not attended before' branch. `actor` is the
        administrator responsible when this is called from the dashboard
        wizard, or None for a public self-registration — either way this
        is the single place a Person/Registration pair gets created, so
        it's the single place the audit trail is written, rather than
        each call site (dashboard wizard, public participant form, public
        worker/pastor form) needing to remember to log it separately.
        """
        person = PersonService.create_person(**person_fields)
        registration = Registration.objects.create(
            person=person, event=event, is_returning_attendee=False, **registration_fields,
        )
        AuditLog.objects.create(
            administrator=actor,
            action=f"Created Person '{person.full_name}' ({person.person_id})"
                   + ('' if actor else ' via public self-registration'),
            model_name='Person', object_id=str(person.pk), ip_address=ip_address or None,
        )
        AuditLog.objects.create(
            administrator=actor,
            action=f"Created Registration '{registration.registration_number}' for {person.full_name} "
                   f"({event.title}, {registration.get_category_display()})"
                   + ('' if actor else ' via public self-registration'),
            model_name='Registration', object_id=str(registration.pk), ip_address=ip_address or None,
        )
        NotificationService.notify(
            title='New Registration',
            message=f"{person.full_name} registered for {event.title} as {registration.get_category_display()}.",
            link_url=f"/dashboard/registrations/{registration.pk}/",
        )
        transaction.on_commit(lambda: send_registration_confirmation_email(registration))
        return RegistrationResult(person=person, registration=registration, person_was_created=True)

    @staticmethod
    @transaction.atomic
    def register_returning_person(
        *, event, person: Person, updated_fields: Optional[dict] = None, registration_fields: dict,
        actor=None, ip_address: str = '',
    ) -> RegistrationResult:
        """'YES, I have attended before' branch — person was already found
        via PersonService.search() by the caller."""
        if Registration.objects.filter(person=person, event=event).exists():
            raise AlreadyRegisteredError(
                f"{person.full_name} ({person.person_id}) is already registered for {event.title}."
            )

        if updated_fields:
            PersonService.update_person(person, **updated_fields)
            AuditLog.objects.create(
                administrator=actor,
                action=f"Updated Person '{person.full_name}' ({person.person_id}) via registration"
                       + ('' if actor else ' — public self-registration'),
                model_name='Person', object_id=str(person.pk), ip_address=ip_address or None,
            )

        registration = Registration.objects.create(
            person=person, event=event, is_returning_attendee=True, **registration_fields,
        )
        AuditLog.objects.create(
            administrator=actor,
            action=f"Created Registration '{registration.registration_number}' for {person.full_name} "
                   f"({event.title}, {registration.get_category_display()}, returning attendee)"
                   + ('' if actor else ' via public self-registration'),
            model_name='Registration', object_id=str(registration.pk), ip_address=ip_address or None,
        )
        NotificationService.notify(
            title='New Registration',
            message=f"{person.full_name} (returning attendee) registered for {event.title} as {registration.get_category_display()}.",
            link_url=f"/dashboard/registrations/{registration.pk}/",
        )
        transaction.on_commit(lambda: send_registration_confirmation_email(registration))
        return RegistrationResult(person=person, registration=registration, person_was_created=False)

    @staticmethod
    def find_returning_person(*, phone_number='', email_address='', person_id='', qr_token='') -> Optional[Person]:
        match = PersonService.search(
            phone_number=phone_number, email_address=email_address,
            person_id=person_id, qr_token=qr_token,
        )
        return match.person if match else None

    @classmethod
    @transaction.atomic
    def _register_public(cls, *, event, person_fields: dict, registration_fields: dict, ip_address: str = '') -> RegistrationResult:
        """
        Shared core of every public, unauthenticated registration entrypoint
        (participant or worker/pastor) — no admin involved, no login. There's
        no visible 'have you attended before?' question here on purpose:
        showing a stranger a lookup that could surface someone else's record
        is a privacy risk unacceptable for an unauthenticated form. Instead
        this matches invisibly, server-side, only against the phone/email
        the visitor themselves just typed — the same dedup guarantee as the
        dashboard wizard, without ever exposing anyone else's data.

        actor is always None here (never passed) — a public submission has
        no administrator to attribute it to; ip_address is recorded on the
        AuditLog entry instead, same as any other unauthenticated write in
        this codebase (e.g. the campaign open-tracking pixel).
        """
        existing = PersonService.search(
            phone_number=person_fields.get('phone_number', ''),
            email_address=person_fields.get('email_address', ''),
        )
        if existing:
            return cls.register_returning_person(
                event=event, person=existing.person, updated_fields=person_fields,
                registration_fields=registration_fields, ip_address=ip_address,
            )
        return cls.register_new_person(
            event=event, person_fields=person_fields, registration_fields=registration_fields,
            ip_address=ip_address,
        )

    @classmethod
    def register_public(
        cls, *, event, person_fields: dict, accommodation_requested: bool = False, ip_address: str = '',
    ) -> RegistrationResult:
        """
        The public self-registration entrypoint for Participants
        (apps/registrations public_views.py). Always registers as a
        Participant — Worker/Pastor self-service goes through
        register_public_worker() instead, which is the only public
        entrypoint allowed to set category='worker'.
        """
        registration_fields = {'category': 'participant', 'accommodation_requested': accommodation_requested}
        return cls._register_public(
            event=event, person_fields=person_fields, registration_fields=registration_fields,
            ip_address=ip_address,
        )

    @classmethod
    def register_public_worker(
        cls, *, event, person_fields: dict, registration_fields: dict, ip_address: str = '',
    ) -> RegistrationResult:
        """
        The public self-registration entrypoint for Workers and Pastors
        (apps/registrations public_views.py / public_forms.WorkerPublicRegistrationForm).
        registration_fields must already carry 'category': 'worker',
        'worker_type', and 'department' — Registration.clean() enforces
        that a department is present for every worker registration, the
        same rule the dashboard wizard follows.
        """
        return cls._register_public(
            event=event, person_fields=person_fields, registration_fields=registration_fields,
            ip_address=ip_address,
        )
