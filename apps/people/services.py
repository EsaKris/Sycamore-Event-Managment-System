"""
Person matching and lifecycle logic.

This is where the spec's central promise lives: "Every individual should
only exist once in the database." All person lookup/creation during
registration MUST go through PersonService rather than touching the
Person model directly, or that guarantee silently breaks.
"""

from dataclasses import dataclass
from typing import Optional

from django.db import transaction

from .models import Person


class DuplicatePersonError(Exception):
    """Raised when an operation would create a second Person for someone
    who already has a record."""


@dataclass
class PersonMatch:
    person: Person
    matched_on: str  # 'phone' | 'email' | 'person_id' | 'qr_token'


class PersonService:

    @staticmethod
    def find_by_phone(phone_number: str) -> Optional[Person]:
        if not phone_number:
            return None
        return Person.objects.filter(phone_number__iexact=phone_number.strip()).first()

    @staticmethod
    def find_by_email(email_address: str) -> Optional[Person]:
        if not email_address:
            return None
        return Person.objects.filter(email_address__iexact=email_address.strip()).first()

    @staticmethod
    def find_by_person_id(person_id: str) -> Optional[Person]:
        if not person_id:
            return None
        return Person.objects.filter(person_id__iexact=person_id.strip()).first()

    @staticmethod
    def find_by_qr_token(qr_token: str) -> Optional[Person]:
        if not qr_token:
            return None
        return Person.objects.filter(qr_token=qr_token).first()

    @classmethod
    def search(cls, *, phone_number: str = '', email_address: str = '',
               person_id: str = '', qr_token: str = '') -> Optional[PersonMatch]:
        """
        Used by the "Have you attended before?" -> YES branch of the
        registration flow. Tries the most reliable identifiers first
        (QR / Person ID are guaranteed-unique; phone/email are the
        practical fallback for someone showing up without their card).
        """
        if qr_token:
            person = cls.find_by_qr_token(qr_token)
            if person:
                return PersonMatch(person, 'qr_token')

        if person_id:
            person = cls.find_by_person_id(person_id)
            if person:
                return PersonMatch(person, 'person_id')

        if phone_number:
            person = cls.find_by_phone(phone_number)
            if person:
                return PersonMatch(person, 'phone')

        if email_address:
            person = cls.find_by_email(email_address)
            if person:
                return PersonMatch(person, 'email')

        return None

    @classmethod
    @transaction.atomic
    def create_person(cls, *, force: bool = False, **fields) -> Person:
        """
        Creates a brand-new Person. Refuses to proceed if a matching
        phone or email already exists, unless `force=True` is explicitly
        passed (e.g. an admin has manually confirmed these are two
        different people who happen to share a contact detail, such as
        a shared family phone).
        """
        if not force:
            existing = cls.search(
                phone_number=fields.get('phone_number', ''),
                email_address=fields.get('email_address', ''),
            )
            if existing:
                raise DuplicatePersonError(
                    f"A person already exists matching this {existing.matched_on} "
                    f"({existing.person.full_name}, {existing.person.person_id}). "
                    f"Did you mean to search for a returning attendee instead?"
                )

        return Person.objects.create(**fields)

    @staticmethod
    @transaction.atomic
    def update_person(person: Person, **fields) -> Person:
        """Update an existing Person's details (e.g. new phone/address
        supplied at a subsequent conference registration)."""
        for key, value in fields.items():
            setattr(person, key, value)
        person.save()
        return person

    @staticmethod
    def delete_person(person: Person, requested_by) -> None:
        """
        The ONLY sanctioned way to remove a Person, and only ever a soft
        delete — per spec, hard deletion is a Super Administrator-only,
        exceptional action and even then this codebase defaults to
        archiving. Wire this up to an explicit confirmation + audit log
        entry at the view layer.
        """
        if not getattr(requested_by, 'is_super_admin', False):
            raise PermissionError('Only the Super Administrator can delete a Person record.')
        person.soft_delete()
