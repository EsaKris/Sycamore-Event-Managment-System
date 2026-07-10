import io

import qrcode
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from .models import Person


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
