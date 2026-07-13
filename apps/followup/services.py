"""
Business logic for the Follow-up Management module — kept thin since this
is mostly straightforward CRUD, but centralized here (rather than in views)
per the project's convention of keeping business logic out of views.
"""

from dataclasses import dataclass
from typing import Optional

from apps.people.models import Person

from .models import FollowUp, FollowUpStatus


@dataclass
class TimelineSummary:
    person: Person
    entries: list
    open_count: int
    overdue_count: int
    last_contact: Optional[FollowUp]


class FollowUpService:

    @staticmethod
    def create_entry(*, person, logged_by=None, **fields) -> FollowUp:
        """`fields` may include: event, follow_up_type, interest_level,
        remarks, outcome, status, next_follow_up_date, officer_assigned."""
        return FollowUp.objects.create(person=person, logged_by=logged_by, **fields)

    @staticmethod
    def get_timeline(person) -> TimelineSummary:
        entries = list(
            FollowUp.objects.filter(person=person)
            .select_related('event', 'officer_assigned', 'logged_by')
            .order_by('-created_at')
        )
        open_count = sum(1 for e in entries if e.status == FollowUpStatus.OPEN)
        overdue_count = sum(1 for e in entries if e.is_overdue)
        return TimelineSummary(
            person=person,
            entries=entries,
            open_count=open_count,
            overdue_count=overdue_count,
            last_contact=entries[0] if entries else None,
        )
