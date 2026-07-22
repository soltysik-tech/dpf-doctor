"""Trip value object: parsed contents of a CarScanner CSV export."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Trip:
    path: str
    start: Optional[datetime]
    duration_s: float
    series: dict[str, list[tuple[float, float]]] = field(default_factory=dict)
