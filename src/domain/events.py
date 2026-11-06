from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(frozen=True)
class EventoDeDominio:
    tipo: str
    agregado_id: str
    version: int
    evento_id: str = field(default_factory=lambda: str(uuid4()))
    ocurrido_en: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )