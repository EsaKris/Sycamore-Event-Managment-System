"""
Implements the QR Scanner page logic from the spec:
    - Live camera scanner / manual code entry (both funnel into `scan()`)
    - Duplicate Scan Warning / Already Checked In / Already Checked Out alerts
    - Immediately-visible person info: photo, name, registration status,
      attendance status, department, worker type, recent attendance
"""

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from django.db import IntegrityError, transaction

from apps.people.models import Person
from apps.registrations.models import Registration

from .models import Attendance, AttendanceSession, CheckType


class ScanStatus(Enum):
    SUCCESS = 'success'
    NOT_FOUND = 'not_found'
    NOT_REGISTERED = 'not_registered'          # person exists, but not registered for this event
    ALREADY_CHECKED_IN = 'already_checked_in'
    ALREADY_CHECKED_OUT = 'already_checked_out'
    NOT_CHECKED_IN_YET = 'not_checked_in_yet'   # trying to check out before ever checking in


# Statuses that represent a real problem worth an error tone, vs a soft warning.
WARNING_STATUSES = {
    ScanStatus.ALREADY_CHECKED_IN,
    ScanStatus.ALREADY_CHECKED_OUT,
    ScanStatus.NOT_CHECKED_IN_YET,
}

MESSAGES = {
    ScanStatus.NOT_FOUND: "No matching person found. Check the code and try again.",
    ScanStatus.NOT_REGISTERED: "This person is not registered for this event.",
    ScanStatus.ALREADY_CHECKED_IN: "Already checked in for this session.",
    ScanStatus.ALREADY_CHECKED_OUT: "Already checked out for this session.",
    ScanStatus.NOT_CHECKED_IN_YET: "Can't check out — no check-in on record for this session yet.",
    ScanStatus.SUCCESS: "Scan recorded.",
}


@dataclass
class ScanOutcome:
    status: ScanStatus
    message: str
    person: Optional[Person] = None
    registration: Optional[Registration] = None
    attendance: Optional[Attendance] = None
    recent_attendance: list = field(default_factory=list)

    @property
    def ok(self):
        return self.status == ScanStatus.SUCCESS

    @property
    def is_warning(self):
        return self.status in WARNING_STATUSES


class AttendanceService:

    @staticmethod
    def find_person(code: str) -> Optional[Person]:
        """Resolves a scanned/typed code to a Person. Tries, in order:
        QR token (UUID), permanent Person ID, phone number."""
        code = (code or '').strip()
        if not code:
            return None

        # QR payloads are emitted as "SEMS:<uuid>" (see Person.qr_payload) but
        # accept a bare UUID too, in case someone scans/types just the token.
        candidate = code.split('SEMS:')[-1].strip()
        try:
            return Person.objects.get(qr_token=uuid.UUID(candidate))
        except (ValueError, Person.DoesNotExist):
            pass

        person = Person.objects.filter(person_id__iexact=code).first()
        if person:
            return person

        return Person.objects.filter(phone_number__iexact=code).first()

    @classmethod
    def _recent_attendance(cls, person: Person, event, limit=5):
        return list(
            person.attendance_records.filter(event=event)
            .select_related('session')
            .order_by('-created_at')[:limit]
        )

    @classmethod
    @transaction.atomic
    def scan(cls, *, code: str, event, session: AttendanceSession, check_type: str, scanner, location: str = '') -> ScanOutcome:
        person = cls.find_person(code)
        if not person:
            return ScanOutcome(status=ScanStatus.NOT_FOUND, message=MESSAGES[ScanStatus.NOT_FOUND])

        registration = (
            Registration.objects.filter(person=person, event=event)
            .select_related('department').first()
        )
        if not registration:
            return ScanOutcome(
                status=ScanStatus.NOT_REGISTERED, message=MESSAGES[ScanStatus.NOT_REGISTERED],
                person=person, recent_attendance=cls._recent_attendance(person, event),
            )

        already = Attendance.objects.filter(person=person, session=session, check_type=check_type).exists()
        if already:
            status = ScanStatus.ALREADY_CHECKED_IN if check_type == CheckType.CHECK_IN else ScanStatus.ALREADY_CHECKED_OUT
            return ScanOutcome(
                status=status, message=MESSAGES[status], person=person, registration=registration,
                recent_attendance=cls._recent_attendance(person, event),
            )

        if check_type == CheckType.CHECK_OUT:
            checked_in = Attendance.objects.filter(person=person, session=session, check_type=CheckType.CHECK_IN).exists()
            if not checked_in:
                return ScanOutcome(
                    status=ScanStatus.NOT_CHECKED_IN_YET, message=MESSAGES[ScanStatus.NOT_CHECKED_IN_YET],
                    person=person, registration=registration,
                    recent_attendance=cls._recent_attendance(person, event),
                )

        try:
            attendance = Attendance.objects.create(
                person=person, registration=registration, event=event, session=session,
                check_type=check_type, scanned_by=scanner, location=location,
            )
        except IntegrityError:
            # Race: two scans landed at once. Treat as "already" rather than a hard error.
            status = ScanStatus.ALREADY_CHECKED_IN if check_type == CheckType.CHECK_IN else ScanStatus.ALREADY_CHECKED_OUT
            return ScanOutcome(
                status=status, message=MESSAGES[status], person=person, registration=registration,
                recent_attendance=cls._recent_attendance(person, event),
            )

        return ScanOutcome(
            status=ScanStatus.SUCCESS, message=MESSAGES[ScanStatus.SUCCESS],
            person=person, registration=registration, attendance=attendance,
            recent_attendance=cls._recent_attendance(person, event),
        )
