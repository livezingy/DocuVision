"""Unit tests for table_band_range (P-028 L1): parser + validator.

Pure logic — no paddle, no server (testing.md local layer). The G2 case
table is pinned: the IE-p079 original case (``40.7-4098MHz``) asserts the
``magnitude_gap`` flag only (X0-9 single-flag ruling); flag order is the
value-domain flags first, then ``magnitude_gap``.
"""

from __future__ import annotations

import pytest

from app.services.table_band_range import BandRange, parse_band_range, validate_band_range

# G2 parse case table: (text, start, end, unit, start_text, end_text);
# all-None-after-text rows = parse miss.
PARSE_CASES = [
    # original IE-p079 case (X0-9: single magnitude_gap flag)
    ("40.7-4098MHz", 40.7, 4098.0, "MHz", "40.7", "4098"),
    # P-002 follow-up secondary evidence case: legal interval
    ("925-960MHz", 925.0, 960.0, "MHz", "925", "960"),
    # whitespace around the dash (control-row form)
    ("40.66 - 40.7 MHz", 40.66, 40.7, "MHz", "40.66", "40.7"),
    # GHz family
    ("1-2GHz", 1.0, 2.0, "GHz", "1", "2"),
    # kHz family
    ("5150-5350kHz", 5150.0, 5350.0, "kHz", "5150", "5350"),
    # Hz family, 6 decades apart
    ("1-1000000Hz", 1.0, 1000000.0, "Hz", "1", "1000000"),
    # thousand-separator spaces fold digit-to-digit
    ("9 600 - 9 800 MHz", 9600.0, 9800.0, "MHz", "9600", "9800"),
    # R2 cache original string folds to 407-4098: legal (gap < 2 decades)
    ("40 7 - 40 98 MHz", 407.0, 4098.0, "MHz", "407", "4098"),
    # negative start
    ("-5-10MHz", -5.0, 10.0, "MHz", "-5", "10"),
    # start > end
    ("10-5MHz", 10.0, 5.0, "MHz", "10", "5"),
    # double flag: negative AND start > end (order pin)
    ("10--5MHz", 10.0, -5.0, "MHz", "10", "-5"),
    # surrounding whitespace tolerated, raw keeps the input verbatim
    ("  40.7-4098MHz ", 40.7, 4098.0, "MHz", "40.7", "4098"),
    # misses: single point (no dash) / no unit / non-numeric / wrong pattern / empty
    ("5.150", None, None, None, None, None),
    ("40.7-4098", None, None, None, None, None),
    ("abc-100MHz", None, None, None, None, None),
    ("40.7 to 40.98 MHz", None, None, None, None, None),
    ("", None, None, None, None, None),
]

# G2 validate case table: (text, expected flags) — parse-hit cases only;
# flag order pinned (value-domain first, then magnitude_gap).
VALIDATE_CASES = [
    ("40.7-4098MHz", ["magnitude_gap"]),               # original case, single flag (X0-9)
    ("925-960MHz", []),                                 # legal
    ("40.66 - 40.7 MHz", []),                           # legal control row
    ("2-30MHz", []),                                    # legal
    ("40-4000MHz", []),                                 # exactly 2.0 decades: strictly-greater threshold
    ("40-4001MHz", ["magnitude_gap"]),                  # just over 2 decades
    ("1-1000000Hz", ["magnitude_gap"]),                 # 6 decades
    ("9 600 - 9 800 MHz", []),                          # legal after fold
    ("40 7 - 40 98 MHz", []),                           # cache-form string: 407-4098, gap < 2
    ("-5-10MHz", ["negative_value"]),
    ("10-5MHz", ["start_gt_end"]),
    ("10--5MHz", ["negative_value", "start_gt_end"]),   # flag order pin
]


def test_parse_case_table() -> None:
    for text, start, end, unit, start_text, end_text in PARSE_CASES:
        br = parse_band_range(text)
        if start is None:
            assert br is None, text
        else:
            assert isinstance(br, BandRange), text
            assert br.start_value == start, text
            assert br.end_value == end, text
            assert br.unit == unit, text
            assert br.start_text == start_text, text
            assert br.end_text == end_text, text
            assert br.raw == text, text


def test_validate_case_table() -> None:
    for text, expected in VALIDATE_CASES:
        br = parse_band_range(text)
        assert br is not None, text
        assert validate_band_range(br) == expected, text


def test_unit_case_folding_is_canonical() -> None:
    for text, unit in [
        ("40.7-4098mhz", "MHz"),
        ("1-2GHZ", "GHz"),
        ("5150-5350KHz", "kHz"),
        ("1-2hz", "Hz"),
    ]:
        br = parse_band_range(text)
        assert br is not None, text
        assert br.unit == unit, text


@pytest.mark.parametrize(
    "text",
    ["5.150", "40.7-4098", "abc-100MHz", "40.7 to 40.98 MHz", ""],
)
def test_parse_misses_return_none(text: str) -> None:
    assert parse_band_range(text) is None
