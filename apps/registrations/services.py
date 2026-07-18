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

from apps.core.services import NotificationService
from apps.people.models import Person
from apps.people.services import DuplicatePersonError, PersonService

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
    def register_new_person(*, event, person_fields: dict, registration_fields: dict) -> RegistrationResult:
        """'NO, I have not attended before' branch."""
        person = PersonService.create_person(**person_fields)
        registration = Registration.objects.create(
            person=person, event=event, is_returning_attendee=False, **registration_fields,
        )
        NotificationService.notify(
            title='New Registration',
            message=f"{person.full_name} registered for {event.title} as {registration.get_category_display()}.",
            link_url=f"/dashboard/registrations/{registration.pk}/",
        )
        return RegistrationResult(person=person, registration=registration, person_was_created=True)

    @staticmethod
    @transaction.atomic
    def register_returning_person(
        *, event, person: Person, updated_fields: Optional[dict] = None, registration_fields: dict,
    ) -> RegistrationResult:
        """'YES, I have attended before' branch — person was already found
        via PersonService.search() by the caller."""
        if Registration.objects.filter(person=person, event=event).exists():
            raise AlreadyRegisteredError(
                f"{person.full_name} ({person.person_id}) is already registered for {event.title}."
            )

        if updated_fields:
            PersonService.update_person(person, **updated_fields)

        registration = Registration.objects.create(
            person=person, event=event, is_returning_attendee=True, **registration_fields,
        )
        NotificationService.notify(
            title='New Registration',
            message=f"{person.full_name} (returning attendee) registered for {event.title} as {registration.get_category_display()}.",
            link_url=f"/dashboard/registrations/{registration.pk}/",
        )
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
    def register_public(cls, *, event, person_fields: dict, accommodation_requested: bool = False) -> RegistrationResult:
        """
        The public self-registration entrypoint (apps/registrations
        public_views.py) — no admin involved, no login. There's no
        visible 'have you attended before?' question here on purpose:
        showing a stranger a lookup that could surface someone else's
        record is a privacy risk unacceptable for an unauthenticated
        form. Instead this matches invisibly, server-side, only against
        the phone/email the visitor themselves just typed — the same
        dedup guarantee as the dashboard wizard, without ever exposing
        anyone else's data.

        Always registers as a Participant — self-service Worker signup
        needs department/coordinator involvement that belongs in the
        dashboard, not a public form.
        """
        registration_fields = {'category': 'participant', 'accommodation_requested': accommodation_requested}

        existing = PersonService.search(
            phone_number=person_fields.get('phone_number', ''),
            email_address=person_fields.get('email_address', ''),
        )
        if existing:
            return cls.register_returning_person(
                event=event, person=existing.person, updated_fields=person_fields,
                registration_fields=registration_fields,
            )
        return cls.register_new_person(event=event, person_fields=person_fields, registration_fields=registration_fields)
