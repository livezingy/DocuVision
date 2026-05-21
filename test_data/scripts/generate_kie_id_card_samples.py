#!/usr/bin/env python3
"""Generate synthetic / desensitized Chinese ID card images for KIE regression.

Outputs to test_data/testfiles/images/kie/:
  - id_card_sample_02.jpg  — clear front
  - id_card_sample_03.jpg  — slight rotation + JPEG compression
  - id_card_sample_04.jpg  — slight blur

All persons, numbers, and addresses are fictional. Safe to commit.
Each image is layout-validated before write (label/value/photo zones must not overlap).
"""

from __future__ import annotations

import io
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

_ROOT = Path(__file__).resolve().parents[2]
_OUT_DIR = _ROOT / "test_data" / "testfiles" / "images" / "kie"

CARD_W, CARD_H = 860, 540
LABEL_X = 40
PHOTO_X = 650
PHOTO_W = 180
CONTENT_RIGHT = PHOTO_X - 16  # max right edge for value text
MIN_LABEL_VALUE_GAP = 16

SAMPLES = [
    {
        "file": "id_card_sample_02.jpg",
        "name": "张伟",
        "id_number": "110101199001011234",
        "date_of_birth": "1990年01月01日",
        "address": "北京市东城区测试路1号",
        "expiration_date": "2030.01.01-2040.01.01",
        "issuing_authority": "北京市公安局东城分局",
        "variant": "clear",
    },
    {
        "file": "id_card_sample_03.jpg",
        "name": "李芳",
        "id_number": "32010219880515231X",
        "date_of_birth": "1988年05月15日",
        "address": "江苏省南京市玄武区示范街道88号",
        "expiration_date": "2025.05.15-2035.05.15",
        "issuing_authority": "南京市公安局玄武分局",
        "variant": "tilted_compressed",
    },
    {
        "file": "id_card_sample_04.jpg",
        "name": "王强",
        "id_number": "440105199203073456",
        "date_of_birth": "1992年03月07日",
        "address": "广东省广州市天河区验收大道100号",
        "expiration_date": "2022.03.07-2032.03.07",
        "issuing_authority": "广州市公安局天河分局",
        "variant": "blurred",
    },
]

ROW_LABELS = ("姓名", "出生", "住址", "有效期限", "签发机关", "公民身份号码")


@dataclass(frozen=True)
class TextBlock:
    role: str  # label | value
    field: str
    text: str
    box: Tuple[int, int, int, int]  # l, t, r, b


@dataclass
class CardFonts:
    title: ImageFont.FreeTypeFont | ImageFont.ImageFont
    label: ImageFont.FreeTypeFont | ImageFont.ImageFont
    value: ImageFont.FreeTypeFont | ImageFont.ImageFont
    small: ImageFont.FreeTypeFont | ImageFont.ImageFont
    id_number: ImageFont.FreeTypeFont | ImageFont.ImageFont
    note: ImageFont.FreeTypeFont | ImageFont.ImageFont


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    if bold:
        candidates = [
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "C:/Windows/Fonts/msyhbd.ttc",
            *candidates,
        ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def load_fonts() -> CardFonts:
    return CardFonts(
        title=_font(28, bold=True),
        label=_font(18),
        value=_font(21, bold=True),
        small=_font(17),
        id_number=_font(24, bold=True),
        note=_font(11),
    )


def _text_bbox(draw: ImageDraw.ImageDraw, xy: Tuple[int, int], text: str, font) -> Tuple[int, int, int, int]:
    x, y = xy
    bbox = draw.textbbox((x, y), text, font=font)
    return bbox[0], bbox[1], bbox[2], bbox[3]


def _boxes_overlap(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int], *, margin: int = 2) -> bool:
    al, at, ar, ab = a
    bl, bt, br, bb = b
    return not (ar + margin <= bl or br + margin <= al or ab + margin <= bt or bb + margin <= at)


def _photo_zone() -> Tuple[int, int, int, int]:
    return PHOTO_X, 86, PHOTO_X + PHOTO_W, 86 + 228


def plan_card_layout(data: dict, fonts: CardFonts) -> Tuple[List[TextBlock], int]:
    """Return text blocks and VALUE_X for a sample (without rasterizing the card)."""
    img = Image.new("RGB", (CARD_W, CARD_H))
    draw = ImageDraw.Draw(img)

    max_label_w = max(_text_bbox(draw, (LABEL_X, 0), label, fonts.label)[2] - LABEL_X for label in ROW_LABELS)
    value_x = LABEL_X + max_label_w + MIN_LABEL_VALUE_GAP

    blocks: List[TextBlock] = []
    y = 90

    def add_pair(field: str, label: str, value: str, value_font, row_gap: int) -> None:
        nonlocal y
        lb = _text_bbox(draw, (LABEL_X, y), label, fonts.label)
        vb = _text_bbox(draw, (value_x, y), value, value_font)
        blocks.append(TextBlock("label", field, label, lb))
        blocks.append(TextBlock("value", field, value, vb))
        y = max(lb[3], vb[3]) + row_gap

    add_pair("name", "姓名", data["name"], fonts.value, 14)
    add_pair("date_of_birth", "出生", data["date_of_birth"], fonts.value, 14)
    add_pair("address", "住址", data["address"], fonts.small, 18)
    add_pair("expiration_date", "有效期限", data["expiration_date"], fonts.small, 14)
    add_pair("issuing_authority", "签发机关", data["issuing_authority"], fonts.small, 20)

    # ID number: label row, then value on its own line (real-card style, avoids horizontal clash)
    id_label = "公民身份号码"
    lb = _text_bbox(draw, (LABEL_X, y), id_label, fonts.label)
    blocks.append(TextBlock("label", "id_number", id_label, lb))
    id_y = lb[3] + 8
    vb = _text_bbox(draw, (LABEL_X, id_y), data["id_number"], fonts.id_number)
    blocks.append(TextBlock("value", "id_number", data["id_number"], vb))

    return blocks, value_x


def validate_layout(blocks: Iterable[TextBlock], *, sample_name: str = "") -> List[str]:
    """Basic format checks: no label/value overlap; text stays left of photo zone."""
    errors: List[str] = []
    blocks = list(blocks)
    photo = _photo_zone()
    prefix = f"{sample_name}: " if sample_name else ""

    for block in blocks:
        l, t, r, b = block.box
        if r > CONTENT_RIGHT and block.role == "value":
            errors.append(f"{prefix}{block.field} value exceeds content column (right={r}, max={CONTENT_RIGHT})")
        if _boxes_overlap(block.box, photo):
            errors.append(f"{prefix}{block.field} {block.role} overlaps photo zone")

    labels = [b for b in blocks if b.role == "label"]
    values = [b for b in blocks if b.role == "value"]
    for label in labels:
        for value in values:
            if label.field != value.field:
                continue
            l_right = label.box[2]
            v_left = value.box[0]
            if v_left < l_right + MIN_LABEL_VALUE_GAP - 2:
                errors.append(
                    f"{prefix}{label.field} label/value too close (label_right={l_right}, value_left={v_left})"
                )
            if _boxes_overlap(label.box, value.box):
                errors.append(f"{prefix}{label.field} label and value boxes overlap")

    # Cross-field vertical sanity: adjacent rows should not overlap
    ordered = sorted(blocks, key=lambda b: (b.box[1], b.box[0]))
    for i, a in enumerate(ordered):
        for b in ordered[i + 1 :]:
            if _boxes_overlap(a.box, b.box):
                errors.append(
                    f"{prefix}rows overlap: {a.field}/{a.role} vs {b.field}/{b.role}"
                )
    return errors


def _draw_base_card(data: dict, fonts: CardFonts, value_x: int) -> Image.Image:
    img = Image.new("RGB", (CARD_W, CARD_H), "#3d7eb8")
    draw = ImageDraw.Draw(img)

    for y in range(0, CARD_H, 6):
        draw.line([(0, y), (CARD_W, y)], fill="#4589c4", width=1)
    for x in range(0, CARD_W, 8):
        draw.line([(x, 0), (x, CARD_H)], fill="#4589c4", width=1)
    draw.rectangle([18, 18, CARD_W - 18, CARD_H - 18], outline="#e8f4ff", width=2)

    draw.text((CARD_W // 2, 36), "中华人民共和国居民身份证", fill="#ffffff", font=fonts.title, anchor="mm")

    px, py = PHOTO_X, 86
    draw.rectangle([px, py, px + PHOTO_W, py + 228], fill="#d8e8f5", outline="#ffffff", width=2)
    draw.text((px + PHOTO_W // 2, py + 114), "照片", fill="#5a7a96", font=fonts.label, anchor="mm")

    y = 90

    def row(label: str, value: str, vfont, gap: int) -> None:
        nonlocal y
        draw.text((LABEL_X, y), label, fill="#e8f4ff", font=fonts.label)
        draw.text((value_x, y), value, fill="#ffffff", font=vfont)
        lb = _text_bbox(draw, (LABEL_X, y), label, fonts.label)
        vb = _text_bbox(draw, (value_x, y), value, vfont)
        y = max(lb[3], vb[3]) + gap

    row("姓名", data["name"], fonts.value, 14)
    row("出生", data["date_of_birth"], fonts.value, 14)
    row("住址", data["address"], fonts.small, 18)
    row("有效期限", data["expiration_date"], fonts.small, 14)
    row("签发机关", data["issuing_authority"], fonts.small, 20)

    draw.text((LABEL_X, y), "公民身份号码", fill="#e8f4ff", font=fonts.label)
    lb = _text_bbox(draw, (LABEL_X, y), "公民身份号码", fonts.label)
    draw.text((LABEL_X, lb[3] + 8), data["id_number"], fill="#ffffff", font=fonts.id_number)

    draw.text((CARD_W - 24, CARD_H - 16), "合成测试样例 · 非真实证件", fill="#b8d4ea", font=fonts.note, anchor="rb")
    return img


def _apply_variant(img: Image.Image, variant: str) -> Image.Image:
    if variant == "clear":
        return img
    if variant == "tilted_compressed":
        rotated = img.rotate(-4.5, expand=True, fillcolor="#2a2a2a")
        rotated = rotated.resize((CARD_W, CARD_H), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        rotated.save(buf, format="JPEG", quality=38, optimize=True)
        buf.seek(0)
        return Image.open(buf).convert("RGB")
    if variant == "blurred":
        out = img.filter(ImageFilter.GaussianBlur(radius=1.15))
        out = ImageEnhance.Brightness(out).enhance(0.92)
        return ImageEnhance.Contrast(out).enhance(0.95)
    return img


def generate_all(out_dir: Path | None = None, *, validate: bool = True) -> list[Path]:
    target = out_dir or _OUT_DIR
    target.mkdir(parents=True, exist_ok=True)
    fonts = load_fonts()
    written: list[Path] = []

    for spec in SAMPLES:
        blocks, value_x = plan_card_layout(spec, fonts)
        if validate:
            errs = validate_layout(blocks, sample_name=spec["file"])
            if errs:
                raise ValueError("Layout validation failed:\n  " + "\n  ".join(errs))

        img = _draw_base_card(spec, fonts, value_x)
        img = _apply_variant(img, spec["variant"])
        path = target / spec["file"]
        quality = 38 if spec["variant"] == "tilted_compressed" else 92
        img.save(path, format="JPEG", quality=quality, optimize=True)
        written.append(path)
        print(f"wrote {path}")
    return written


if __name__ == "__main__":
    try:
        generate_all()
    except ValueError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
