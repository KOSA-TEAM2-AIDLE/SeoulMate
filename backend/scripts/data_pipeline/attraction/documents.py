from datetime import date
import hashlib
from typing import Iterable

from scripts.data_pipeline.attraction.models import ProcessedPlace, RAGDocument
from domains.attraction.taxonomy import category_metadata


def build_documents(places: Iterable[ProcessedPlace], *, generated_on: date) -> list[RAGDocument]:
    documents: list[RAGDocument] = []
    for place in places:
        lines = [
            f"Name: {place.name}", f"Category: {place.category}", f"Summary: {place.summary}",
            f"Description: {place.description}", f"Address: {place.road_address}",
            f"Hours: {place.hours}", f"Fee: {place.fee}", f"Tags: {place.tags}",
        ]
        if place.kind == "event":
            lines.insert(2, f"Period: {place.start_date or ''} to {place.end_date or ''}")
        content = "\n".join(line for line in lines if line.split(": ", 1)[1])
        document_id = f"{place.kind}:{place.place_key}:{place.lang}"
        metadata = {
            "place_key": place.place_key, "source_cid": place.source_cid, "lang": place.lang,
            "kind": place.kind, "category": place.category, "road_address": place.road_address,
            "latitude": place.latitude, "longitude": place.longitude, "start_date": str(place.start_date or ""),
            "end_date": str(place.end_date or ""), "homepage_url": place.homepage_url,
            "generated_on": generated_on.isoformat(),
        }
        metadata.update(category_metadata(place.category, place.kind))
        documents.append(RAGDocument(document_id, content, metadata, hashlib.sha256(content.encode()).hexdigest()))
    return documents
