import json
from pathlib import Path
from typing import Any

import shapefile
from shapely import make_valid
from shapely.geometry import mapping, shape


REQUIRED_FIELDS = {"AREA_CD", "AREA_NM", "CATEGORY"}


class PoiConversionError(Exception):
    """공식 POI Shapefile을 변환할 수 없을 때 발생."""


def read_poi_shapefile(shapefile_path: Path) -> dict[str, Any]:
    if not shapefile_path.exists():
        raise PoiConversionError(f"Shapefile을 찾을 수 없습니다: {shapefile_path}")

    try:
        reader = shapefile.Reader(str(shapefile_path), encoding="utf-8")
    except (OSError, shapefile.ShapefileException) as exc:
        raise PoiConversionError("공식 POI Shapefile을 열 수 없습니다.") from exc

    field_names = {field[0] for field in reader.fields[1:]}
    missing_fields = REQUIRED_FIELDS - field_names
    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise PoiConversionError(f"필수 DBF 필드가 없습니다: {missing}")

    features: list[dict[str, Any]] = []
    for shape_record in reader.iterShapeRecords():
        record = shape_record.record.as_dict()
        geometry = make_valid(shape(shape_record.shape.__geo_interface__))
        if geometry.geom_type not in {"Polygon", "MultiPolygon"}:
            area_code = str(record["AREA_CD"]).strip()
            raise PoiConversionError(
                f"POI 도형을 Polygon으로 보정할 수 없습니다: {area_code}"
            )
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "area_code": str(record["AREA_CD"]).strip(),
                    "area_name": str(record["AREA_NM"]).strip(),
                    "category": str(record["CATEGORY"]).strip(),
                },
                "geometry": mapping(geometry),
            }
        )

    return {"type": "FeatureCollection", "features": features}


def write_poi_geojson(shapefile_path: Path, output_path: Path) -> int:
    geojson = read_poi_shapefile(shapefile_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(geojson, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return len(geojson["features"])
