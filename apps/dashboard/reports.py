"""
Reports module. Per spec, reports are needed for: Registrations,
Attendance, Departments, Workers, Participants, Pastors, Churches,
States, Countries, Accommodation, Follow-up, Email Campaigns,
Administrator Activity — exportable to PDF/Excel/CSV.

Rather than one hand-built report per named item (Participants, Pastors,
Churches, States... are all just the Registrations report sliced a
different way), this ships a handful of report *types* whose row-level
data already carries every column needed to slice by any of those
dimensions once exported — matching how a front-desk admin actually
works with these exports (open in Excel, filter/pivot as needed).

Each report type is a (label, columns, row_fn) tuple registered in
REPORT_TYPES. `row_fn(event)` returns a list of dicts keyed by column.
"""

from apps.attendance.models import Attendance
from apps.campaigns.models import EmailCampaign
from apps.core.models import AuditLog
from apps.departments.models import Department
from apps.followup.models import FollowUp
from apps.registrations.models import Registration


def _registrations_rows(event=None):
    qs = Registration.objects.select_related('person', 'event', 'department').order_by('event__year', 'person__last_name')
    if event:
        qs = qs.filter(event=event)
    rows = []
    for r in qs:
        rows.append({
            'Event': r.event.title,
            'Person ID': r.person.person_id,
            'Full Name': r.person.full_name,
            'Phone': r.person.phone_number,
            'Email': r.person.email_address,
            'Category': r.get_category_display(),
            'Worker Type': r.get_worker_type_display() if r.worker_type else '',
            'Department': r.department.name if r.department else '',
            'Church': r.person.church_name,
            'State': r.person.state,
            'Country': r.person.country,
            'Accommodation Requested': 'Yes' if r.accommodation_requested else 'No',
            'Returning Attendee': 'Yes' if r.is_returning_attendee else 'No',
            'Status': r.get_status_display(),
            'Registration Number': r.registration_number,
            'Registered At': r.created_at.strftime('%Y-%m-%d %H:%M'),
        })
    return rows


def _attendance_rows(event=None):
    qs = Attendance.objects.select_related('person', 'event', 'session', 'scanned_by').order_by('-created_at')
    if event:
        qs = qs.filter(event=event)
    rows = []
    for a in qs:
        rows.append({
            'Event': a.event.title,
            'Person ID': a.person.person_id,
            'Full Name': a.person.full_name,
            'Session': a.session.label,
            'Type': a.get_check_type_display(),
            'Scanned By': (a.scanned_by.get_full_name() or a.scanned_by.username) if a.scanned_by else '',
            'Timestamp': a.created_at.strftime('%Y-%m-%d %H:%M'),
        })
    return rows


def _departments_rows(event=None):
    regs = Registration.objects.filter(department__isnull=False).select_related('department', 'event')
    if event:
        regs = regs.filter(event=event)
    counts = {}
    for r in regs:
        key = (r.department.name, r.event.title)
        counts[key] = counts.get(key, 0) + 1
    rows = [
        {'Department': dept, 'Event': ev, 'Worker Count': count}
        for (dept, ev), count in sorted(counts.items())
    ]
    if not event:
        # Also include departments with zero registrations, for completeness.
        seen_depts = {dept for dept, _ in counts.keys()}
        for d in Department.objects.exclude(name__in=seen_depts):
            rows.append({'Department': d.name, 'Event': '(all)', 'Worker Count': 0})
    return rows


def _followup_rows(event=None):
    qs = FollowUp.objects.select_related('person', 'event', 'officer_assigned', 'logged_by').order_by('-created_at')
    if event:
        qs = qs.filter(event=event)
    rows = []
    for f in qs:
        rows.append({
            'Person ID': f.person.person_id,
            'Full Name': f.person.full_name,
            'Event': f.event.title if f.event else '',
            'Type': f.get_follow_up_type_display(),
            'Interest Level': f.get_interest_level_display() if f.interest_level else '',
            'Outcome': f.get_outcome_display(),
            'Status': f.get_status_display(),
            'Next Follow-up': f.next_follow_up_date.strftime('%Y-%m-%d') if f.next_follow_up_date else '',
            'Officer Assigned': (f.officer_assigned.get_full_name() or f.officer_assigned.username) if f.officer_assigned else '',
            'Logged By': (f.logged_by.get_full_name() or f.logged_by.username) if f.logged_by else '',
            'Logged At': f.created_at.strftime('%Y-%m-%d %H:%M'),
        })
    return rows


def _campaigns_rows(event=None):
    qs = EmailCampaign.objects.select_related('template', 'event').order_by('-created_at')
    if event:
        qs = qs.filter(event=event)
    rows = []
    for c in qs:
        recipients = c.recipients.all()
        rows.append({
            'Campaign': c.name,
            'Event': c.event.title if c.event else '(all events)',
            'Template': c.template.name,
            'Status': c.get_status_display(),
            'Recipients': recipients.count(),
            'Sent': recipients.filter(status='sent').count() + recipients.filter(status='opened').count(),
            'Opened': recipients.filter(status='opened').count(),
            'Failed': recipients.filter(status='failed').count(),
            'Sent At': c.sent_at.strftime('%Y-%m-%d %H:%M') if c.sent_at else '',
        })
    return rows


def _admin_activity_rows(event=None):
    # Activity logs aren't event-scoped, so `event` is accepted for a
    # consistent function signature but intentionally unused here.
    qs = AuditLog.objects.select_related('administrator').order_by('-created_at')[:1000]
    rows = []
    for log in qs:
        rows.append({
            'Timestamp': log.created_at.strftime('%Y-%m-%d %H:%M'),
            'Administrator': (log.administrator.get_full_name() or log.administrator.username) if log.administrator else 'System',
            'Action': log.action,
            'Model': log.model_name,
            'Object ID': log.object_id,
            'IP Address': log.ip_address or '',
        })
    return rows


REPORT_TYPES = {
    'registrations': {'label': 'Registrations', 'row_fn': _registrations_rows, 'event_scoped': True},
    'attendance': {'label': 'Attendance', 'row_fn': _attendance_rows, 'event_scoped': True},
    'departments': {'label': 'Departments & Workers', 'row_fn': _departments_rows, 'event_scoped': True},
    'followup': {'label': 'Follow-up', 'row_fn': _followup_rows, 'event_scoped': True},
    'campaigns': {'label': 'Email Campaigns', 'row_fn': _campaigns_rows, 'event_scoped': True},
    'admin_activity': {'label': 'Administrator Activity', 'row_fn': _admin_activity_rows, 'event_scoped': False},
}


def get_report_rows(report_key: str, event=None):
    spec = REPORT_TYPES.get(report_key)
    if not spec:
        return [], []
    rows = spec['row_fn'](event if spec['event_scoped'] else None)
    columns = list(rows[0].keys()) if rows else []
    return columns, rows
