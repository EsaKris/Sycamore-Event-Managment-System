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
        return RegistrationResult(person=person, registration=registration, person_was_created=False)

    @staticmethod
    def find_returning_person(*, phone_number='', email_address='', person_id='', qr_token='') -> Optional[Person]:
        match = PersonService.search(
            phone_number=phone_number, email_address=email_address,
            person_id=person_id, qr_token=qr_token,
        )
        return match.person if match else None
