"""
ID Card generation. Cards are rendered on the fly from Registration +
Person + Event data — nothing is stored on disk, mirroring the QR image
approach from the Attendance phase (apps/people/views.py).

Two distinct layouts, chosen by Registration.category:
  - Participants get the light, white-background card (cheap to print,
    matches the public-facing brand).
  - Workers and Pastors get a dark, sidebar-style card so staff/serving
    team and pastors are instantly distinguishable from attendees at a
    glance — at check-in, on a lanyard, or from across a room.

Card size: CR80 (standard badge/ID card), landscape, at 300 DPI —
3.370in x 2.125in = 1011x638px.
"""

import io
import os
from functools import lru_cache

import qrcode
from PIL import Image, ImageDraw, ImageFont

from .models import RegistrationCategory

FONTS_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'fonts')
SPACE_GROTESK = os.path.join(FONTS_DIR, 'SpaceGrotesk.ttf')
INTER = os.path.join(FONTS_DIR, 'Inter.ttf')

CARD_W, CARD_H = 1011, 638
DPI = 300

INK = (28, 30, 38)
MUTED = (110, 116, 132)
LIGHT_BORDER = (226, 228, 234)
WHITE = (255, 255, 255)

# Worker/Pastor card palette — fixed (not event.color_theme) so the dark
# design always has reliable contrast, and so a worker/pastor badge always
# reads the same regardless of which event's accent colour is in play.
WORKER_GOLD = (212, 162, 76)
WORKER_MUTED = (158, 164, 178)
WORKER_LINE = (60, 64, 76)


def _hex_to_rgb(hex_color: str):
    hex_color = (hex_color or '#7C3AED').lstrip('#')
    if len(hex_color) != 6:
        hex_color = '7C3AED'
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


@lru_cache(maxsize=None)
def _font(path: str, size: int, weight: int, opsz: int = None):
    font = ImageFont.truetype(path, size)
    try:
        axes = font.get_variation_axes()
        if opsz is not None and len(axes) == 2:
            font.set_variation_by_axes([opsz, weight])
        else:
            font.set_variation_by_axes([weight])
    except Exception:
        pass  # static font or variation unsupported — use as-is
    return font


def display_font(size, weight=700):
    return _font(SPACE_GROTESK, size, weight)


def body_font(size, weight=400):
    return _font(INTER, size, weight, opsz=min(max(size, 14), 32))


def _draw_rounded_rect(draw, box, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _fit_text(draw, text, font_path, weight, max_width, start_size, min_size=14):
    size = start_size
    while size > min_size:
        font = _font(font_path, size, weight)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 2
    return _font(font_path, min_size, weight)


def _person_photo(person, size):
    """Returns a square PIL image for the photo slot — the person's
    uploaded photo cropped/resized, or an initials avatar as fallback."""
    if person.photo:
        try:
            img = Image.open(person.photo.path).convert('RGB')
            w, h = img.size
            side = min(w, h)
            left, top = (w - side) // 2, (h - side) // 2
            img = img.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)
            return img
        except Exception:
            pass  # missing/corrupt file on disk — fall through to initials

    img = Image.new('RGB', (size, size), (232, 184, 94))
    draw = ImageDraw.Draw(img)
    initials = f"{person.first_name[:1]}{person.last_name[:1]}".upper()
    font = display_font(int(size * 0.38), 700)
    bbox = draw.textbbox((0, 0), initials, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]), initials, font=font, fill=(26, 19, 5))
    return img


def _render_participant_card(registration) -> Image.Image:
    """Light, white-background layout — Participants only."""
    person = registration.person
    event = registration.event
    accent = _hex_to_rgb(event.color_theme)

    card = Image.new('RGB', (CARD_W, CARD_H), WHITE)
    draw = ImageDraw.Draw(card)

    # Top accent bar
    bar_h = 84
    draw.rectangle([0, 0, CARD_W, bar_h], fill=accent)
    draw.text((36, 20), 'SEMS', font=display_font(26, 700), fill=WHITE)
    event_font = _fit_text(draw, event.title, SPACE_GROTESK, 600, CARD_W - 220, 22, 14)
    ev_bbox = draw.textbbox((0, 0), event.title, font=event_font)
    draw.text((CARD_W - 36 - (ev_bbox[2] - ev_bbox[0]), 28), event.title, font=event_font, fill=WHITE)

    # Photo
    photo_size = 190
    photo_x, photo_y = 40, bar_h + 34
    photo = _person_photo(person, photo_size)
    mask = Image.new('L', (photo_size, photo_size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, photo_size, photo_size], radius=18, fill=255)
    card.paste(photo, (photo_x, photo_y), mask)
    draw.rounded_rectangle(
        [photo_x, photo_y, photo_x + photo_size, photo_y + photo_size], radius=18, outline=LIGHT_BORDER, width=2,
    )

    # Person ID under photo
    pid_font = body_font(15, 600)
    pid_bbox = draw.textbbox((0, 0), person.person_id, font=pid_font)
    draw.text((photo_x + (photo_size - (pid_bbox[2] - pid_bbox[0])) / 2, photo_y + photo_size + 12),
              person.person_id, font=pid_font, fill=MUTED)

    # Name + badge + details column
    col_x = photo_x + photo_size + 32
    col_w = CARD_W - col_x - 190

    name_font = _fit_text(draw, person.full_name, SPACE_GROTESK, 700, col_w, 40, 22)
    draw.text((col_x, bar_h + 38), person.full_name, font=name_font, fill=INK)

    # Category badge pill
    badge_text = registration.card_label.upper()
    badge_font = body_font(16, 700)
    bb = draw.textbbox((0, 0), badge_text, font=badge_font)
    pad_x, pad_y = 14, 8
    pill_w, pill_h = (bb[2] - bb[0]) + pad_x * 2, (bb[3] - bb[1]) + pad_y * 2
    pill_y = bar_h + 92
    _draw_rounded_rect(draw, [col_x, pill_y, col_x + pill_w, pill_y + pill_h], radius=pill_h / 2, fill=accent)
    draw.text((col_x + pad_x - bb[0], pill_y + pad_y - bb[1]), badge_text, font=badge_font, fill=WHITE)

    # Department / worker type line
    detail_y = pill_y + pill_h + 18
    detail_bits = []
    if registration.department:
        detail_bits.append(registration.department.name)
    if registration.worker_type and not registration.badge_label:
        pass  # already reflected in the badge itself
    detail_line = ' · '.join(detail_bits)
    if detail_line:
        draw.text((col_x, detail_y), detail_line, font=body_font(16, 600), fill=INK)
        detail_y += 26

    if person.church_name:
        church_font = _fit_text(draw, person.church_name, SPACE_GROTESK, 400, col_w, 15, 11)
        draw.text((col_x, detail_y), person.church_name, font=body_font(14, 400), fill=MUTED)

    # QR code, bottom-right
    qr = qrcode.QRCode(border=1, box_size=6)
    qr.add_data(person.qr_payload)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color=(28, 30, 38), back_color='white').convert('RGB')
    qr_size = 132
    qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)
    qr_x, qr_y = CARD_W - qr_size - 40, CARD_H - qr_size - 80
    card.paste(qr_img, (qr_x, qr_y))

    # Footer strip
    footer_y = CARD_H - 46
    draw.line([(0, footer_y), (CARD_W, footer_y)], fill=LIGHT_BORDER, width=2)
    draw.text((36, footer_y + 12), f"{event.start_date:%b %d}\u2013{event.end_date:%b %d, %Y}",
               font=body_font(14, 500), fill=MUTED)
    scan_text = 'Scan to check in'
    sc_font = body_font(13, 600)
    sc_bbox = draw.textbbox((0, 0), scan_text, font=sc_font)
    draw.text((qr_x + (qr_size - (sc_bbox[2] - sc_bbox[0])) / 2, qr_y - 22), scan_text, font=sc_font, fill=MUTED)

    return card


def _render_worker_card(registration) -> Image.Image:
    """
    Dark, sidebar-style layout — Workers & Pastors only. Deliberately
    different at a glance from the participant card (dark ink body vs.
    white, gold accent sidebar vs. a thin top bar) so staff, ushers, and
    security can tell a serving-team member or pastor apart from an
    attendee across a room, not just up close. Department is called out
    large and gold since that's the one detail someone checking a badge
    actually needs.
    """
    person = registration.person
    event = registration.event

    card = Image.new('RGB', (CARD_W, CARD_H), INK)
    draw = ImageDraw.Draw(card)

    # --- Sidebar ---
    sidebar_w = 300
    draw.rectangle([0, 0, sidebar_w, CARD_H], fill=WORKER_GOLD)
    draw.text((28, 24), 'SEMS', font=display_font(24, 700), fill=INK)

    photo_size = 176
    photo_x = (sidebar_w - photo_size) // 2
    photo_y = 96
    photo = _person_photo(person, photo_size)
    mask = Image.new('L', (photo_size, photo_size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, photo_size, photo_size], radius=16, fill=255)
    card.paste(photo, (photo_x, photo_y), mask)
    draw.rounded_rectangle(
        [photo_x, photo_y, photo_x + photo_size, photo_y + photo_size], radius=16, outline=INK, width=3,
    )

    pid_font = body_font(15, 700)
    pid_bbox = draw.textbbox((0, 0), person.person_id, font=pid_font)
    draw.text((sidebar_w / 2 - (pid_bbox[2] - pid_bbox[0]) / 2, photo_y + photo_size + 16),
               person.person_id, font=pid_font, fill=INK)

    role_text = (registration.get_worker_type_display() if registration.worker_type else 'Staff').upper()
    role_font = body_font(14, 700)
    role_bbox = draw.textbbox((0, 0), role_text, font=role_font)
    draw.text((sidebar_w / 2 - (role_bbox[2] - role_bbox[0]) / 2, CARD_H - 56),
              role_text, font=role_font, fill=INK)

    # --- Main dark area ---
    col_x = sidebar_w + 44
    col_w = CARD_W - col_x - 190

    event_font = _fit_text(draw, event.title, SPACE_GROTESK, 600, col_w, 18, 12)
    ev_bbox = draw.textbbox((0, 0), event.title, font=event_font)
    draw.text((CARD_W - 36 - (ev_bbox[2] - ev_bbox[0]), 30), event.title, font=event_font, fill=WORKER_MUTED)

    name_font = _fit_text(draw, person.full_name, SPACE_GROTESK, 700, col_w, 38, 22)
    draw.text((col_x, 62), person.full_name, font=name_font, fill=WHITE)

    # Category badge pill — the manual override or worker-type text, same
    # rule as the participant card, just recoloured for the dark body.
    badge_text = registration.card_label.upper()
    badge_font = body_font(16, 700)
    bb = draw.textbbox((0, 0), badge_text, font=badge_font)
    pad_x, pad_y = 14, 8
    pill_w, pill_h = (bb[2] - bb[0]) + pad_x * 2, (bb[3] - bb[1]) + pad_y * 2
    pill_y = 118
    _draw_rounded_rect(draw, [col_x, pill_y, col_x + pill_w, pill_y + pill_h], radius=pill_h / 2, fill=WORKER_GOLD)
    draw.text((col_x + pad_x - bb[0], pill_y + pad_y - bb[1]), badge_text, font=badge_font, fill=INK)

    # Department — the one detail a check-in coordinator or usher actually
    # needs, so it's the largest text on the card after the name.
    detail_y = pill_y + pill_h + 26
    if registration.department:
        dept_font = _fit_text(draw, registration.department.name, SPACE_GROTESK, 600, col_w, 26, 16)
        draw.text((col_x, detail_y), registration.department.name, font=dept_font, fill=WORKER_GOLD)
        detail_y += 38

    if person.church_name:
        church_font = _fit_text(draw, person.church_name, SPACE_GROTESK, 400, col_w, 15, 11)
        draw.text((col_x, detail_y), person.church_name, font=body_font(14, 400), fill=WORKER_MUTED)

    # QR code, bottom-right, on a white chip so it stays scannable against
    # the dark card body.
    qr = qrcode.QRCode(border=1, box_size=6)
    qr.add_data(person.qr_payload)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color=INK, back_color='white').convert('RGB')
    qr_size = 124
    qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)
    qr_pad = 10
    qr_x, qr_y = CARD_W - qr_size - 40, CARD_H - qr_size - 76
    _draw_rounded_rect(
        draw, [qr_x - qr_pad, qr_y - qr_pad, qr_x + qr_size + qr_pad, qr_y + qr_size + qr_pad],
        radius=12, fill=WHITE,
    )
    card.paste(qr_img, (qr_x, qr_y))

    scan_text = 'Scan to check in'
    sc_font = body_font(13, 600)
    sc_bbox = draw.textbbox((0, 0), scan_text, font=sc_font)
    draw.text((qr_x + (qr_size - (sc_bbox[2] - sc_bbox[0])) / 2, qr_y - qr_pad - 22),
               scan_text, font=sc_font, fill=WORKER_MUTED)

    # Footer strip
    footer_y = CARD_H - 46
    draw.line([(sidebar_w, footer_y), (CARD_W, footer_y)], fill=WORKER_LINE, width=2)
    draw.text((col_x, footer_y + 12), f"{event.start_date:%b %d}\u2013{event.end_date:%b %d, %Y}",
               font=body_font(14, 500), fill=WORKER_MUTED)

    return card


def render_card(registration) -> Image.Image:
    """Dispatches to the layout for this registration's category —
    Workers/Pastors get the dark sidebar card, everyone else gets the
    light participant card."""
    if registration.category == RegistrationCategory.WORKER:
        return _render_worker_card(registration)
    return _render_participant_card(registration)


def render_card_png(registration) -> bytes:
    buffer = io.BytesIO()
    render_card(registration).save(buffer, format='PNG', dpi=(DPI, DPI))
    return buffer.getvalue()


def render_card_pdf(registration) -> bytes:
    buffer = io.BytesIO()
    render_card(registration).save(buffer, format='PDF', resolution=DPI)
    return buffer.getvalue()


def render_cards_pdf(registrations) -> bytes:
    """Bulk print: one page per registration, in a single PDF."""
    images = [render_card(r) for r in registrations]
    if not images:
        raise ValueError('No registrations to render.')
    buffer = io.BytesIO()
    images[0].save(buffer, format='PDF', resolution=DPI, save_all=True, append_images=images[1:])
    return buffer.getvalue()
