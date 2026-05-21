#!/usr/bin/env python3
"""生成 KIE 合成卡证测试图（非真实证件，仅供 OCR/VL 验收）。

若本机无 Python/Pillow，验收样例可置于 test_data/testfiles/images/kie/
（见该目录 README；当前文件可由仓库既有 IDCard/Passport/BankCard 图复制）。
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_ROOT = Path(__file__).resolve().parents[2]
_OUT = _ROOT / "test_data" / "testfiles" / "images" / "kie"

_WATERMARK = "合成测试样例 · 非真实证件"


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("msyh.ttc", "simhei.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_watermark(draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
    draw.text((12, h - 28), _WATERMARK, fill=(180, 40, 40), font=_font(14))


def gen_id_card(path: Path) -> None:
    w, h = 856, 540
    img = Image.new("RGB", (w, h), (230, 245, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, w, 80), fill=(0, 90, 160))
    draw.text((24, 22), "中华人民共和国居民身份证", fill="white", font=_font(28))
    draw.text((420, 120), "姓名  测试用户", fill=(20, 20, 20), font=_font(26))
    draw.text((420, 175), "性别  男    民族  汉", fill=(20, 20, 20), font=_font(22))
    draw.text((420, 225), "出生  1990年01月01日", fill=(20, 20, 20), font=_font(22))
    draw.text((420, 275), "住址  北京市海淀区测试路1号", fill=(20, 20, 20), font=_font(20))
    draw.text((420, 340), "公民身份号码", fill=(20, 20, 20), font=_font(22))
    draw.text((420, 375), "110101199001011234", fill=(10, 10, 10), font=_font(30))
    draw.rectangle((40, 120, 360, 420), outline=(0, 90, 160), width=3)
    draw.text((80, 250), "照片区", fill=(120, 120, 120), font=_font(24))
    _draw_watermark(draw, w, h)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")


def gen_passport(path: Path) -> None:
    w, h = 900, 620
    img = Image.new("RGB", (w, h), (20, 55, 100))
    draw = ImageDraw.Draw(img)
    draw.rectangle((30, 30, w - 30, h - 30), fill=(245, 240, 230))
    draw.text((50, 40), "PASSPORT / 护照", fill=(20, 20, 20), font=_font(26))
    draw.text((50, 100), "Surname/Given name  ZHANG / CESHI", fill=(20, 20, 20), font=_font(22))
    draw.text((50, 150), "Nationality  CHN", fill=(20, 20, 20), font=_font(22))
    draw.text((50, 200), "Date of birth  01 JAN 1990", fill=(20, 20, 20), font=_font(22))
    draw.text((50, 250), "Sex  M", fill=(20, 20, 20), font=_font(22))
    draw.text((50, 300), "Place of birth  BEIJING", fill=(20, 20, 20), font=_font(22))
    draw.text((50, 360), "Passport No.  E12345678", fill=(10, 10, 10), font=_font(28))
    draw.text((50, 420), "Date of issue  01 JAN 2020", fill=(20, 20, 20), font=_font(22))
    draw.text((50, 470), "Date of expiry  01 JAN 2030", fill=(20, 20, 20), font=_font(22))
    draw.text((50, 520), "Authority  MPS Exit & Entry", fill=(20, 20, 20), font=_font(20))
    _draw_watermark(draw, w, h)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")


def gen_bank_card(path: Path) -> None:
    w, h = 860, 540
    img = Image.new("RGB", (w, h), (25, 25, 35))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((40, 60, w - 40, h - 60), radius=24, fill=(35, 85, 160))
    draw.text((70, 100), "测试银行 TEST BANK", fill="white", font=_font(28))
    draw.text((70, 200), "6222 0001 2345 6789", fill="white", font=_font(36))
    draw.text((70, 300), "VALID THRU  12/28", fill=(220, 220, 220), font=_font(24))
    draw.text((70, 360), "CESHI YONGHU", fill="white", font=_font(26))
    draw.text((70, 420), "借记卡 DEBIT", fill=(200, 200, 200), font=_font(22))
    _draw_watermark(draw, w, h)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")


def main() -> None:
    gen_id_card(_OUT / "id_card_sample_01.png")
    gen_passport(_OUT / "passport_sample_01.png")
    gen_bank_card(_OUT / "bank_card_sample_01.png")
    print(f"Wrote 3 samples under {_OUT}")


if __name__ == "__main__":
    main()
