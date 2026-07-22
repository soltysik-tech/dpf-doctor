"""Authoritative PID registry for CarScanner exports.

One table, one classifier. Every stage that consumes CarScanner CSVs classifies
PID strings through this module; unit metadata is available for renderers.

Registry ordering rule: longer overlapping needles come first, because
classification is substring-match first-hit-wins.
"""
from typing import Optional

# (needle, key, unit) - unit may be None when we don't rely on it.
_ENTRIES: tuple[tuple[str, str, Optional[str]], ...] = (
    ("Regeneration in progress", "regen", None),
    ("DPF differential pressure", "dpf_dp", "kPa"),
    ("DPF/GPF soot", "soot_trig", "%"),
    ("Average Time Between PF Regens", "avg_t_regen", "s"),
    ("Average Distance Between PF Regens", "avg_d_regen", "km"),
    ("Distance since last regeneration", "d_since_regen", "km"),
    ("Total distance travelled", "odo_total", "km"),
    ("Distance travelled", "trip_dist", "km"),
    ("Vehicle speed", "speed", "km/h"),
    ("Engine RPM x1000", "rpm_k", "krpm"),
    ("Engine RPM", "rpm", "rpm"),
    ("Engine coolant temperature", "coolant_t", "C"),
    ("Engine oil temperature", "oil_t", "C"),
    ("Intake air temperature", "iat", "C"),
    ("Oil level", "oil_lvl", "%"),
    ("NOx adsorber regeneration status", "nox_regen", None),
    ("EGR system control", "egr_duty", "%"),
    ("MAF air flow rate", "maf", "g/s"),
    ("Calculated engine load value", "load", "%"),
    ("Throttle position", "tps", "%"),
    ("Instantaneous fuel consumption (l/100 km)", "fuel_l100", "l/100km"),
    ("Instantaneous fuel consumption", "fuel_rate", "l/h"),
    ("Power from MAF", "power_maf", "kW"),
)

NEEDLES: tuple[tuple[str, str], ...] = tuple((n, k) for n, k, _ in _ENTRIES)
PID_KEYS: tuple[str, ...] = tuple(k for _, k, _ in _ENTRIES)
_UNITS: dict[str, Optional[str]] = {k: u for _, k, u in _ENTRIES}

_cache: dict[str, Optional[str]] = {}


def classify(pid: str) -> Optional[str]:
    """Map a CarScanner PID string to a canonical key, or None if unknown."""
    if pid in _cache:
        return _cache[pid]
    result: Optional[str] = None
    for needle, key in NEEDLES:
        if needle in pid:
            result = key
            break
    _cache[pid] = result
    return result


def unit_of(key: str) -> Optional[str]:
    """Return the display unit for a canonical key, or None if unspecified."""
    return _UNITS.get(key)
