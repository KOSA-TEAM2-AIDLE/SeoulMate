from datetime import date
from typing import Iterable

from scripts.data_pipeline.attraction.transform import classify_and_filter_rows


def build_review_targets(rows: Iterable[dict[str, object]], *, as_of: date) -> list[dict[str, object]]:
    filtered = classify_and_filter_rows(rows, as_of=as_of)
    targets = []
    for place in [*filtered.attractions, *filtered.events]:
        if not place.road_address or place.latitude is None or place.longitude is None:
            continue
        targets.append({
            "place_key": place.place_key, "cid": place.source_cid, "lang": place.lang,
            "kind": place.kind, "category": place.category, "name": place.name,
            "road_address": place.road_address, "latitude": place.latitude, "longitude": place.longitude,
        })
    return targets
