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
    image_url: str
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


@dataclass(frozen=True)
class AttractionPlaceRecord:
    id: str
    source_cid: str
    language: str
    kind: str
    name: str
    category: str
    category_primary: str
    category_secondary: str
    summary: str
    description: str
    tags: str
    address: str
    latitude: float | None
    longitude: float | None
    hours: str
    fee: str
    image: str | None
    link: str | None
    start_date: date | None
    end_date: date | None
    rating: float | None
    review_count: int
    english_review_count: int
    foreign_review_count: int

    @property
    def embedding_content(self) -> str:
        lines = [
            f"Name: {self.name}",
            f"Kind: {self.kind}",
            f"Category: {self.category}",
            f"Summary: {self.summary}",
            f"Description: {self.description}",
            f"Tags: {self.tags}",
            f"Address: {self.address}",
            f"Hours: {self.hours}",
            f"Fee: {self.fee}",
        ]
        if self.kind == "event":
            lines.append(
                f"Event period: {self.start_date or ''} to {self.end_date or ''}"
            )
        return "\n".join(
            line for line in lines if line.split(": ", 1)[1].strip()
        )


@dataclass(frozen=True)
class AttractionReviewRecord:
    source_review_id: str
    attraction_id: str
    language: str
    rating: float | None
    content: str


@dataclass(frozen=True)
class AttractionCleaningReport:
    language: str
    source_places: int
    cleaned_places: int
    attractions: int
    active_events: int
    expired_events: int
    invalid_event_dates: int
    source_reviews: int
    cleaned_reviews: int
    orphan_reviews: int
    empty_reviews: int


@dataclass(frozen=True)
class CleanedAttractionDataset:
    language: str
    places: tuple[AttractionPlaceRecord, ...]
    reviews: tuple[AttractionReviewRecord, ...]
    report: AttractionCleaningReport
