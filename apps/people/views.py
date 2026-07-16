import io

import qrcode
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView

from .models import Person


class PersonListView(LoginRequiredMixin, ListView):
    login_url = 'dashboard:login'
    model = Person
    template_name = 'people/list.html'
    context_object_name = 'people'
    paginate_by = 30

    def get_queryset(self):
        qs = Person.objects.order_by('-created_at')
        q = self.request.GET.get('q', '').strip()
        state = self.request.GET.get('state', '')
        country = self.request.GET.get('country', '')
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q) | Q(last_name__icontains=q)
                | Q(phone_number__icontains=q) | Q(email_address__icontains=q)
                | Q(person_id__iexact=q)
            )
        if state:
            qs = qs.filter(state__iexact=state)
        if country:
            qs = qs.filter(country__iexact=country)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['query'] = self.request.GET.get('q', '')
        ctx['selected_state'] = self.request.GET.get('state', '')
        ctx['selected_country'] = self.request.GET.get('country', '')
        ctx['states'] = Person.objects.exclude(state='').values_list('state', flat=True).distinct().order_by('state')
        ctx['countries'] = Person.objects.exclude(country='').values_list('country', flat=True).distinct().order_by('country')
        ctx['total_count'] = self.get_queryset().count()
        return ctx


class PersonDetailView(LoginRequiredMixin, DetailView):
    login_url = 'dashboard:login'
    model = Person
    template_name = 'people/detail.html'
    context_object_name = 'person'
    slug_field = 'person_id'
    slug_url_kwarg = 'person_id'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        person = self.object
        ctx['registrations'] = person.registrations.select_related('event', 'department').order_by('-created_at')
        ctx['follow_ups'] = person.follow_ups.select_related('event', 'officer_assigned').order_by('-created_at')[:5]
        ctx['attendance_records'] = person.attendance_records.select_related('event', 'session').order_by('-created_at')[:8]
        return ctx


@login_required(login_url='dashboard:login')
def person_qr_image(request, person_id):
    """
    Renders a Person's permanent QR code as a PNG on the fly. Nothing is
    stored on disk — the token itself is the permanent, stable part
    (Person.qr_token never changes), so the image can always be
    regenerated identically.
    """
    person = get_object_or_404(Person, person_id=person_id)

    qr = qrcode.QRCode(border=1, box_size=8)
    qr.add_data(person.qr_payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#0B0E14', back_color='#FFFFFF')

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return HttpResponse(buffer.getvalue(), content_type='image/png')
