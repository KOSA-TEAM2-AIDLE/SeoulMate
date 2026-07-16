from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class ProcessedPlace:
    place_key: str
    source_cid: str
    lang: str
    kind: str
    category: str
    name: str
    summary: str
    description: str
    road_address: str
    latitude: float | None
    longitude: float | None
    hours: str
    fee: str
    tags: str
    homepage_url: str
    start_date: date | None
    end_date: date | None


@dataclass(frozen=True)
class QuarantineRow:
    source_cid: str
    place_key: str
    name: str
    reason: str


@dataclass(frozen=True)
class FilterResult:
    attractions: list[ProcessedPlace]
    events: list[ProcessedPlace]
    quarantine: list[QuarantineRow]


@dataclass(frozen=True)
class RAGDocument:
    document_id: str
    content: str
    metadata: dict[str, Any]
    content_hash: str
