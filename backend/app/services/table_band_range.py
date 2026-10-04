"""Band-range pattern validation for merged frequency cells (P-028 L1).

Pure functions, no IO, no state. ``parse_band_range`` recognises the
「number - number - unit」 pattern (unit family MHz/GHz/kHz/Hz, case-folded,
thousand-separator spaces folded digit-to-digit); ``validate_band_range``
returns flag strings for the value-domain checks and the magnitude gap.
Pattern-driven only (no semantic column detection): cells that do not parse
are not touched. The backfill hook (P-028 L2) only flags — it never rewrites
cell data (no silent correction, no decimal-point guessing).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class BandRange:
    """A parsed 「start - end unit」 interval (values in the named unit)."""

    start_value: float
    end_value: float
    unit: str
    raw: str
    start_text: str
    end_text: str


# Thousand-separator spaces fold before matching ("9 600" -> "9600"); the
# fold is digit-to-digit only, so it cannot bridge the dash separator.
_THOUSANDS_SPACE_RE = re.compile(r"(?<=\d)[ \t]+(?=\d)")
_BAND_RANGE_RE = re.compile(
    r"^(?P<start>[+-]?\d+(?:\.\d+)?)\s*-\s*(?P<end>[+-]?\d+(?:\.\d+)?)\s*"
    r"(?P<unit>mhz|ghz|khz|hz)$",
    re.IGNORECASE,
)

_UNIT_CANONICAL = {"mhz": "MHz", "ghz": "GHz", "khz": "kHz", "hz": "Hz"}


def parse_band_range(text: str) -> Optional[BandRange]:
    """Parse the 「number - number - unit」 pattern; None when not hit.

    Whitespace around the dash is allowed ("40.66 - 40.7 MHz"); the unit is
    required and case-folded to its canonical spelling; thousand-separator
    spaces collapse ("40 7" -> "407"). ``raw`` keeps the input verbatim.
    """
    if not text:
        return None
    folded = _THOUSANDS_SPACE_RE.sub("", text.strip())
    m = _BAND_RANGE_RE.match(folded)
    if m is None:
        return None
    start_text = m.group("start")
    end_text = m.group("end")
    return BandRange(
        start_value=float(start_text),
        end_value=float(end_text),
        unit=_UNIT_CANONICAL[m.group("unit").lower()],
        raw=text,
        start_text=start_text,
        end_text=end_text,
    )


def validate_band_range(br: BandRange) -> List[str]:
    """Value-domain flags first (negative / non-finite / start>end), then the
    magnitude gap: unit-unified ``|log10(start) - log10(end)| > 2`` decades.
    Empty list = the interval is legal. Values <= 0 or non-finite skip the
    log check (already flagged by the domain checks)."""
    flags: List[str] = []
    if br.start_value < 0 or br.end_value < 0:
        flags.append("negative_value")
    if not (math.isfinite(br.start_value) and math.isfinite(br.end_value)):
        flags.append("non_finite")
    if br.start_value > br.end_value:
        flags.append("start_gt_end")
    if (
        "non_finite" not in flags
        and br.start_value > 0
        and br.end_value > 0
        and abs(math.log10(br.start_value) - math.log10(br.end_value)) > 2
    ):
        flags.append("magnitude_gap")
    return flags
