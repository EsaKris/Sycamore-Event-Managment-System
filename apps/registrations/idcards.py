"""
ID Card generation. Cards are rendered on the fly from Registration +
Person + Event data — nothing is stored on disk, mirroring the QR image
approach from the Attendance phase (apps/people/views.py). One card
design serves every category; only the badge text/colour and which
optional lines are shown change.

Card size: CR80 (standard badge/ID card), landscape, at 300 DPI —
3.370in x 2.125in = 1011x638px. Printed cards use a white background
regardless of the dashboard's dark theme, since that's how badges are
actually printed (and it saves ink).
"""

import io
import os
from functools import lru_cache

import qrcode
from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'fonts')
SPACE_GROTESK = os.path.join(FONTS_DIR, 'SpaceGrotesk.ttf')
INTER = os.path.join(FONTS_DIR, 'Inter.ttf')

CARD_W, CARD_H = 1011, 638
DPI = 300

INK = (28, 30, 38)
MUTED = (110, 116, 132)
LIGHT_BORDER = (226, 228, 234)
WHITE = (255, 255, 255)


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


def render_card(registration) -> Image.Image:
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
