"""
Global Search — the topbar search bar, live since Phase 2 but never wired
up until now. Searches across the identifiers people actually use to find
things in this system: names, phone/email, Person IDs, registration
numbers, event titles, department names.

Deliberately NOT a generic full-text search framework — just the handful
of models where "find this thing quickly" matters, each capped to a small
result count so the dropdown stays fast and scannable.
"""

from dataclasses import dataclass, field
from typing import List

from django.db.models import Q
from django.urls import reverse

from apps.accounts.models import User
from apps.departments.models import Department
from apps.events.models import Event
from apps.people.models import Person
from apps.registrations.models import Registration

RESULT_LIMIT_PER_GROUP = 5


@dataclass
class SearchResult:
    title: str
    subtitle: str
    url: str
    icon: str  # a short key the template maps to an SVG


@dataclass
class SearchGroup:
    label: str
    results: List[SearchResult] = field(default_factory=list)


def global_search(query: str, *, user=None) -> List[SearchGroup]:
    query = (query or '').strip()
    if len(query) < 2:
        return []

    groups = []

    people = Person.objects.filter(
        Q(first_name__icontains=query) | Q(last_name__icontains=query)
        | Q(phone_number__icontains=query) | Q(email_address__icontains=query)
        | Q(person_id__iexact=query)
    ).order_by('-created_at')[:RESULT_LIMIT_PER_GROUP]
    if people:
        groups.append(SearchGroup('People', [
            SearchResult(
                title=p.full_name, subtitle=f"{p.person_id} · {p.phone_number}",
                url=reverse('followup:timeline', args=[p.person_id]), icon='person',
            ) for p in people
        ]))

    registrations = Registration.objects.filter(
        Q(registration_number__icontains=query) | Q(person__first_name__icontains=query)
        | Q(person__last_name__icontains=query)
    ).select_related('person', 'event').order_by('-created_at')[:RESULT_LIMIT_PER_GROUP]
    if registrations:
        groups.append(SearchGroup('Registrations', [
            SearchResult(
                title=f"{r.person.full_name} — {r.registration_number}", subtitle=r.event.title,
                url=reverse('registrations:detail', args=[r.pk]), icon='registration',
            ) for r in registrations
        ]))

    events = Event.objects.filter(title__icontains=query).order_by('-year')[:RESULT_LIMIT_PER_GROUP]
    if events:
        groups.append(SearchGroup('Events', [
            SearchResult(
                title=ev.title, subtitle=f"{ev.start_date:%b %Y}" if ev.start_date else '',
                url=reverse('attendance:scanner') + f'?event={ev.id}', icon='event',
            ) for ev in events
        ]))

    departments = Department.objects.filter(name__icontains=query)[:RESULT_LIMIT_PER_GROUP]
    if departments:
        groups.append(SearchGroup('Departments', [
            SearchResult(
                title=d.name, subtitle='Department',
                url=reverse('registrations:list') + f'?department={d.id}', icon='department',
            ) for d in departments
        ]))

    if getattr(user, 'is_super_admin', False):
        admins = User.objects.filter(
            Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query),
        )[:RESULT_LIMIT_PER_GROUP]
        if admins:
            groups.append(SearchGroup('Administrators', [
                SearchResult(
                    title=a.get_full_name() or a.username, subtitle=f"@{a.username} · {a.get_role_display()}",
                    url=reverse('accounts:list'), icon='admin',
                ) for a in admins
            ]))

    return groups
