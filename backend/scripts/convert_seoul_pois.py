from core.config import DATA_DIR
from services.poi_converter import write_poi_geojson


SOURCE = DATA_DIR / "seoul_poi" / "raw" / "seoul_poi_areas.shp"
OUTPUT = DATA_DIR / "seoul_poi" / "processed" / "seoul_poi_areas.geojson"


def main() -> None:
    count = write_poi_geojson(SOURCE, OUTPUT)
    print(f"{count}개 POI 영역을 변환했습니다: {OUTPUT}")


if __name__ == "__main__":
    main()
