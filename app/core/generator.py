from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re

import fitz
from PIL import Image, ImageDraw, ImageFont
import qrcode

from app.models.profile import TemplateProfile


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^\w\-\.]+", "_", value.strip(), flags=re.UNICODE)
    return cleaned[:120] or "output"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    color = hex_color.strip().lstrip("#")
    if len(color) != 6:
        return (0, 0, 0)
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))


def _hex_to_pdf_rgb(hex_color: str) -> tuple[float, float, float]:
    r, g, b = _hex_to_rgb(hex_color)
    return (r / 255.0, g / 255.0, b / 255.0)


def generate_qr_image(content: str, size: int) -> Image.Image:
    qr = qrcode.QRCode(border=1, box_size=12)
    qr.add_data(content)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    return img.resize((size, size), Image.Resampling.LANCZOS)


def _load_font(profile: TemplateProfile) -> ImageFont.ImageFont:
    if profile.font_path and Path(profile.font_path).exists():
        try:
            return ImageFont.truetype(profile.font_path, profile.font_size)
        except OSError:
            pass
    # Fallback to common scalable system fonts so size changes are visible.
    for font_name in ("arial.ttf", "segoeui.ttf", "calibri.ttf", "tahoma.ttf"):
        try:
            return ImageFont.truetype(font_name, profile.font_size)
        except OSError:
            continue
    return ImageFont.load_default()


def _output_path_for_record(
    output_dir: str | Path,
    person_name: str,
    coupon_code: str,
    extension: str,
) -> Path:
    person_token = sanitize_filename(person_name)
    coupon_token = sanitize_filename(coupon_code)
    filename = f"{person_token}_{coupon_token}.{extension}"
    base_path = Path(output_dir) / filename
    if not base_path.exists():
        return base_path
    # Keep deterministic prefix but avoid accidental overwrite in duplicate rows.
    for index in range(1, 10000):
        candidate = base_path.with_name(f"{base_path.stem}_{index}{base_path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError("Could not allocate a unique output filename.")


def render_image_record(
    template_path: str | Path,
    profile: TemplateProfile,
    person_name: str,
    coupon_code: str,
    output_path: str | Path,
    logo_path: str | Path | None = None,
) -> None:
    base = Image.open(template_path).convert("RGBA")
    qr_img = generate_qr_image(coupon_code, profile.qr_size)
    base.paste(qr_img, (int(profile.qr_x), int(profile.qr_y)), qr_img)

    if profile.logo_enabled and logo_path and Path(logo_path).exists():
        logo_img = Image.open(logo_path).convert("RGBA").resize(
            (profile.logo_width, profile.logo_height), Image.Resampling.LANCZOS
        )
        base.paste(logo_img, (int(profile.logo_x), int(profile.logo_y)), logo_img)

    draw = ImageDraw.Draw(base)
    draw.text(
        (int(profile.name_x), int(profile.name_y)),
        person_name,
        fill=_hex_to_rgb(profile.text_color_hex),
        font=_load_font(profile),
    )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    ext = output.suffix.lower()
    if ext == ".pdf":
        base.convert("RGB").save(output, "PDF", resolution=300.0)
    elif ext in {".jpg", ".jpeg"}:
        base.convert("RGB").save(output, "JPEG", quality=95)
    else:
        base.save(output, "PNG")


def render_pdf_record(
    template_path: str | Path,
    profile: TemplateProfile,
    person_name: str,
    coupon_code: str,
    output_path: str | Path,
    logo_path: str | Path | None = None,
) -> None:
    template_bytes = Path(template_path).read_bytes()
    doc = fitz.open(stream=template_bytes, filetype="pdf")
    page = doc[0]

    if profile.preview_width <= 0 or profile.preview_height <= 0:
        raise ValueError("Invalid preview dimensions in profile.")
    scale_x = page.rect.width / profile.preview_width
    scale_y = page.rect.height / profile.preview_height

    qr_img = generate_qr_image(coupon_code, profile.qr_size)
    qr_bytes = BytesIO()
    qr_img.save(qr_bytes, format="PNG")
    qr_w = profile.qr_size * scale_x
    qr_h = profile.qr_size * scale_y
    qr_rect = fitz.Rect(
        profile.qr_x * scale_x,
        profile.qr_y * scale_y,
        profile.qr_x * scale_x + qr_w,
        profile.qr_y * scale_y + qr_h,
    )
    page.insert_image(qr_rect, stream=qr_bytes.getvalue())

    if profile.logo_enabled and logo_path and Path(logo_path).exists():
        logo_bytes = Path(logo_path).read_bytes()
        logo_rect = fitz.Rect(
            profile.logo_x * scale_x,
            profile.logo_y * scale_y,
            profile.logo_x * scale_x + (profile.logo_width * scale_x),
            profile.logo_y * scale_y + (profile.logo_height * scale_y),
        )
        page.insert_image(logo_rect, stream=logo_bytes)

    page.insert_text(
        fitz.Point(profile.name_x * scale_x, profile.name_y * scale_y),
        person_name,
        fontsize=max(6, profile.font_size * ((scale_x + scale_y) / 2.0)),
        color=_hex_to_pdf_rgb(profile.text_color_hex),
    )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)
    doc.close()


def render_pdf_record_as_image(
    template_path: str | Path,
    profile: TemplateProfile,
    person_name: str,
    coupon_code: str,
    output_path: str | Path,
    logo_path: str | Path | None = None,
) -> None:
    doc = fitz.open(template_path)
    page = doc[0]

    if profile.preview_width <= 0 or profile.preview_height <= 0:
        doc.close()
        raise ValueError("Invalid preview dimensions in profile.")

    zoom_x = profile.preview_width / page.rect.width
    zoom_y = profile.preview_height / page.rect.height
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom_x, zoom_y), alpha=False)
    base = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGBA")

    qr_img = generate_qr_image(coupon_code, profile.qr_size)
    base.paste(qr_img, (int(profile.qr_x), int(profile.qr_y)), qr_img)

    if profile.logo_enabled and logo_path and Path(logo_path).exists():
        logo_img = Image.open(logo_path).convert("RGBA").resize(
            (profile.logo_width, profile.logo_height), Image.Resampling.LANCZOS
        )
        base.paste(logo_img, (int(profile.logo_x), int(profile.logo_y)), logo_img)

    draw = ImageDraw.Draw(base)
    draw.text(
        (int(profile.name_x), int(profile.name_y)),
        person_name,
        fill=_hex_to_rgb(profile.text_color_hex),
        font=_load_font(profile),
    )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    ext = output.suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        base.convert("RGB").save(output, "JPEG", quality=95)
    else:
        base.save(output, "PNG")

    doc.close()


def generate_record(
    template_path: str | Path,
    profile: TemplateProfile,
    person_name: str,
    coupon_code: str,
    output_dir: str | Path,
    logo_path: str | Path | None = None,
) -> Path:
    template_is_pdf = profile.template_kind == "pdf" or Path(template_path).suffix.lower() == ".pdf"
    out_ext = profile.output_format.lower() or "pdf"
    if out_ext not in {"pdf", "png", "jpg", "jpeg"}:
        out_ext = "pdf"
    output_path = _output_path_for_record(output_dir, person_name, coupon_code, out_ext)

    if template_is_pdf:
        if profile.preview_width <= 0 or profile.preview_height <= 0:
            raise ValueError(
                "PDF template metadata is missing. Please load the PDF using the Template Browse button first."
            )
        if out_ext == "pdf":
            render_pdf_record(
                template_path=template_path,
                profile=profile,
                person_name=person_name,
                coupon_code=coupon_code,
                output_path=output_path,
                logo_path=logo_path,
            )
        else:
            render_pdf_record_as_image(
                template_path=template_path,
                profile=profile,
                person_name=person_name,
                coupon_code=coupon_code,
                output_path=output_path,
                logo_path=logo_path,
            )
    else:
        render_image_record(
            template_path=template_path,
            profile=profile,
            person_name=person_name,
            coupon_code=coupon_code,
            output_path=output_path,
            logo_path=logo_path,
        )
    return output_path

