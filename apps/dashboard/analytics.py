"""
Aggregation queries backing the Analytics page. Returns plain dicts
(labels/datasets) that the template serializes straight into Chart.js
via json_script — no separate AJAX round trip needed since this is all
cheap aggregate SQL, not row-level data.
"""

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from apps.attendance.models import Attendance, CheckType
from apps.campaigns.models import EmailCampaign, RecipientStatus
from apps.people.models import Gender, Person
from apps.registrations.models import Registration


def _daily_trend(queryset, days=30):
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)
    counts = {d: 0 for d in (start + timedelta(n) for n in range(days))}
    for row in queryset.filter(created_at__date__gte=start).values('created_at__date').annotate(total=Count('id')):
        d = row['created_at__date']
        if d in counts:
            counts[d] = row['total']
    return {
        'labels': [d.strftime('%b %d') for d in counts.keys()],
        'data': list(counts.values()),
    }


def _age_bucket(dob, today):
    if not dob:
        return None
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if age < 18:
        return 'Under 18'
    if age <= 25:
        return '18–25'
    if age <= 35:
        return '26–35'
    if age <= 45:
        return '36–45'
    if age <= 60:
        return '46–60'
    return '60+'


def build_analytics(event=None):
    registrations = Registration.objects.all()
    attendance = Attendance.objects.all()
    if event:
        registrations = registrations.filter(event=event)
        attendance = attendance.filter(event=event)

    people = Person.objects.filter(registrations__in=registrations).distinct()

    # --- Trends ---
    registration_trend = _daily_trend(registrations)
    attendance_trend = _daily_trend(attendance.filter(check_type=CheckType.CHECK_IN))

    # --- Gender ---
    gender_labels = dict(Gender.choices)
    gender_counts = people.values('gender').annotate(total=Count('id')).order_by('gender')
    gender = {
        'labels': [gender_labels.get(g['gender'], 'Unspecified') for g in gender_counts],
        'data': [g['total'] for g in gender_counts],
    }

    # --- Age distribution ---
    today = timezone.localdate()
    bucket_order = ['Under 18', '18–25', '26–35', '36–45', '46–60', '60+']
    bucket_counts = {b: 0 for b in bucket_order}
    for dob in people.exclude(date_of_birth__isnull=True).values_list('date_of_birth', flat=True):
        bucket = _age_bucket(dob, today)
        if bucket:
            bucket_counts[bucket] += 1
    age_distribution = {'labels': bucket_order, 'data': [bucket_counts[b] for b in bucket_order]}

    # --- State / Country ---
    state_counts = (
        people.exclude(state='').values('state').annotate(total=Count('id')).order_by('-total')[:10]
    )
    state_distribution = {'labels': [s['state'] for s in state_counts], 'data': [s['total'] for s in state_counts]}

    country_counts = (
        people.exclude(country='').values('country').annotate(total=Count('id')).order_by('-total')[:10]
    )
    country_distribution = {'labels': [c['country'] for c in country_counts], 'data': [c['total'] for c in country_counts]}

    # --- Returning vs first-time ---
    returning_count = registrations.filter(is_returning_attendee=True).count()
    first_time_count = registrations.filter(is_returning_attendee=False).count()
    returning_split = {'labels': ['Returning', 'First-time'], 'data': [returning_count, first_time_count]}

    # --- Departments ---
    dept_counts = (
        registrations.exclude(department__isnull=True)
        .values('department__name').annotate(total=Count('id')).order_by('-total')[:10]
    )
    departments = {'labels': [d['department__name'] for d in dept_counts], 'data': [d['total'] for d in dept_counts]}

    # --- Email campaign stats (last 5 campaigns) ---
    campaigns = EmailCampaign.objects.order_by('-created_at')[:5]
    campaign_labels, sent_data, opened_data, failed_data = [], [], [], []
    for c in campaigns:
        recipients = c.recipients.all()
        campaign_labels.append(c.name[:24])
        sent_data.append(recipients.filter(status=RecipientStatus.SENT).count())
        opened_data.append(recipients.filter(status=RecipientStatus.OPENED).count())
        failed_data.append(recipients.filter(status=RecipientStatus.FAILED).count())
    campaign_stats = {
        'labels': list(reversed(campaign_labels)),
        'sent': list(reversed(sent_data)),
        'opened': list(reversed(opened_data)),
        'failed': list(reversed(failed_data)),
    }

    return {
        'registration_trend': registration_trend,
        'attendance_trend': attendance_trend,
        'gender': gender,
        'age_distribution': age_distribution,
        'state_distribution': state_distribution,
        'country_distribution': country_distribution,
        'returning_split': returning_split,
        'departments': departments,
        'campaign_stats': campaign_stats,
        'totals': {
            'registrations': registrations.count(),
            'people': people.count(),
            'attendance_scans': attendance.count(),
            'campaigns_sent': EmailCampaign.objects.filter(status='sent').count(),
        },
    }
