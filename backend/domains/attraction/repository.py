"""언어별 관광지·리뷰 pgvector 검색 Repository."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
import json
from typing import Any, Literal, Protocol

from core.config import DB_CONFIG, OPENAI_API_KEY, OPENAI_EMBED_DIM, OPENAI_EMBED_MODEL


Language = Literal["ko", "en"]
PROFILE_LIMIT = 300
REVIEW_POOL = 200
REVIEWS_PER_PLACE = 5


class QueryEmbedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


@dataclass(frozen=True)
class AttractionVectorHit:
    attraction_id: str
    rank: int
    similarity: float


@dataclass(frozen=True)
class ReviewVectorHit:
    review_id: int
    attraction_id: str
    content: str
    rank: int
    similarity: float
    word_count: int


@dataclass(frozen=True)
class AttractionRecord:
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


@dataclass(frozen=True)
class AttractionRetrievalResult:
    query: str
    language: Language
    profile_hits: tuple[AttractionVectorHit, ...]
    review_hits_by_place: dict[str, tuple[ReviewVectorHit, ...]]
    attractions: dict[str, AttractionRecord]
    query_vector: tuple[float, ...]


class OpenAIQueryEmbedder:
    def __init__(self) -> None:
        from openai import OpenAI

        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않습니다.")
        self._client = OpenAI(api_key=OPENAI_API_KEY)

    def embed(self, text: str) -> list[float]:
        query = text.strip()
        if not query:
            raise ValueError("관광 Vector 검색어는 비어 있을 수 없습니다.")
        response = self._client.embeddings.create(
            model=OPENAI_EMBED_MODEL,
            input=query,
            dimensions=OPENAI_EMBED_DIM,
        )
        return response.data[0].embedding


def _connection():
    import psycopg2
    return psycopg2.connect(**DB_CONFIG)


def _language(value: str) -> Language:
    return "en" if value.casefold().startswith("en") else "ko"


def _tables(language: Language) -> dict[str, str]:
    return {
        "attraction": f"attraction_{language}",
        "profile": f"attraction_embedding_{language}",
        "review": f"attraction_review_{language}",
        "review_embedding": f"attraction_review_embedding_{language}",
    }


def _literal(vector: Sequence[float]) -> str:
    if not vector:
        raise ValueError("검색 Vector는 비어 있을 수 없습니다.")
    return json.dumps([float(value) for value in vector], separators=(",", ":"))


class AttractionRepository:
    implemented = True

    def __init__(self, *, connection_factory: Callable[[], Any] | None = None, embedder: QueryEmbedder | None = None) -> None:
        self._connection_factory = connection_factory or _connection
        self._embedder = embedder

    def embed_query(self, query: str) -> list[float]:
        if self._embedder is None:
            self._embedder = OpenAIQueryEmbedder()
        return self._embedder.embed(query)

    def search_profiles(self, vector: Sequence[float], *, language: str, as_of: date, limit: int = PROFILE_LIMIT) -> tuple[AttractionVectorHit, ...]:
        tables = _tables(_language(language))
        literal = _literal(vector)
        with self._connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT e.attraction_id, 1 - (e.embedding <=> %s::vector) AS similarity
                FROM {tables['profile']} e
                JOIN {tables['attraction']} a ON a.id = e.attraction_id
                WHERE a.kind = 'attraction' OR a.end_date IS NULL OR a.end_date >= %s
                ORDER BY e.embedding <=> %s::vector, e.attraction_id
                LIMIT %s
                """,
                (literal, as_of, literal, limit),
            )
            rows = cursor.fetchall()
        return tuple(AttractionVectorHit(str(row[0]), rank, float(row[1])) for rank, row in enumerate(rows, 1))

    def search_reviews(self, vector: Sequence[float], *, language: str, pool: int = REVIEW_POOL, per_place: int = REVIEWS_PER_PLACE) -> dict[str, tuple[ReviewVectorHit, ...]]:
        tables = _tables(_language(language))
        literal = _literal(vector)
        with self._connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT review_id, attraction_id, content,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM {tables['review_embedding']}
                ORDER BY embedding <=> %s::vector, review_id
                LIMIT %s
                """,
                (literal, literal, pool),
            )
            rows = cursor.fetchall()
        grouped: dict[str, list[ReviewVectorHit]] = {}
        for rank, (review_id, attraction_id, content, similarity) in enumerate(rows, 1):
            hits = grouped.setdefault(str(attraction_id), [])
            if len(hits) < per_place:
                text = str(content).strip()
                hits.append(ReviewVectorHit(int(review_id), str(attraction_id), text, rank, float(similarity), len(text.split())))
        return {place_id: tuple(hits) for place_id, hits in grouped.items()}

    def fetch_attractions(self, ids: Sequence[str], *, language: str) -> dict[str, AttractionRecord]:
        normalized = list(dict.fromkeys(str(value) for value in ids))
        if not normalized:
            return {}
        table = _tables(_language(language))["attraction"]
        with self._connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT id, source_cid, language, kind, name, category,
                       category_primary, category_secondary, summary, description,
                       tags, address, latitude, longitude, hours, fee, image, link,
                       start_date, end_date, rating, review_count,
                       english_review_count, foreign_review_count
                FROM {table} WHERE id = ANY(%s)
                """,
                (normalized,),
            )
            rows = cursor.fetchall()
        return {str(row[0]): AttractionRecord(*row) for row in rows}

    def fetch_supporting_reviews(self, vector: Sequence[float], ids: Sequence[str], *, language: str, per_place: int = REVIEWS_PER_PLACE) -> dict[str, tuple[ReviewVectorHit, ...]]:
        normalized = list(dict.fromkeys(str(value) for value in ids))
        if not normalized:
            return {}
        table = _tables(_language(language))["review_embedding"]
        literal = _literal(vector)
        with self._connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT review_id, attraction_id, content, similarity, place_rank
                FROM (
                    SELECT review_id, attraction_id, content,
                           1 - (embedding <=> %s::vector) AS similarity,
                           ROW_NUMBER() OVER (PARTITION BY attraction_id ORDER BY embedding <=> %s::vector, review_id) AS place_rank
                    FROM {table} WHERE attraction_id = ANY(%s)
                ) ranked WHERE place_rank <= %s ORDER BY attraction_id, place_rank
                """,
                (literal, literal, normalized, per_place),
            )
            rows = cursor.fetchall()
        grouped: dict[str, list[ReviewVectorHit]] = {}
        for review_id, attraction_id, content, similarity, place_rank in rows:
            text = str(content).strip()
            grouped.setdefault(str(attraction_id), []).append(ReviewVectorHit(int(review_id), str(attraction_id), text, int(place_rank), float(similarity), len(text.split())))
        return {place_id: tuple(hits) for place_id, hits in grouped.items()}

    def retrieve(self, query: str, *, language: str, as_of: date) -> AttractionRetrievalResult:
        normalized_language = _language(language)
        vector = self.embed_query(query)
        profiles = self.search_profiles(vector, language=normalized_language, as_of=as_of)
        reviews = self.search_reviews(vector, language=normalized_language)
        ids = list(dict.fromkeys([*(hit.attraction_id for hit in profiles), *reviews.keys()]))
        return AttractionRetrievalResult(query, normalized_language, profiles, reviews, self.fetch_attractions(ids, language=normalized_language), tuple(vector))


__all__ = ["AttractionRecord", "AttractionRepository", "AttractionRetrievalResult", "AttractionVectorHit", "ReviewVectorHit"]
