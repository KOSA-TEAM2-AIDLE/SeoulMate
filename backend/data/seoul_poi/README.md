# 서울시 주요 장소 POI 영역

## 출처

- 제공처: 서울 열린데이터광장
- 데이터셋: 서울시 실시간 인구데이터
- 원본 파일: 서울시 주요 121장소 영역
- 확인일: 2026-07-14
- 좌표계: WGS84 (EPSG:4326)
- 문자 인코딩: UTF-8

## 디렉터리

```text
seoul_poi/
├── raw/                         # 서울시 배포 원본
│   ├── seoul_poi_areas.cpg
│   ├── seoul_poi_areas.dbf
│   ├── seoul_poi_areas.prj
│   ├── seoul_poi_areas.shp
│   └── seoul_poi_areas.shx
└── processed/
    └── seoul_poi_areas.geojson  # Backend 런타임용 변환 결과
```

Shapefile은 같은 기본 이름의 다섯 파일이 모두 있어야 정상적으로 읽을 수 있다.
QGIS 메타데이터인 `.qmd`는 Backend 변환에 필요하지 않다.

## 변환

`backend` 디렉터리에서 실행한다.

```bash
uv run python -m scripts.convert_seoul_pois
```

변환기는 DBF의 `AREA_CD`, `AREA_NM`, `CATEGORY`를 GeoJSON 속성으로
정규화한다. 원본 `POI070`의 자기교차 도형을 포함해 유효하지 않은 Polygon은
Shapely의 `make_valid()`로 보정한다.

## 위치 매핑 정책

1. 좌표를 `Point(longitude, latitude)`로 생성한다.
2. Point를 포함하거나 경계에 두는 POI Polygon을 찾는다.
3. 여러 Polygon이 겹치면 면적이 가장 작은 영역을 구체적인 POI로 선택한다.
4. 포함 영역이 없으면 Polygon 경계까지 거리가 가장 가까운 POI를 선택한다.
5. 기본 2km를 초과하면 `PoiNotSupportedError`를 발생시킨다.

GeoJSON의 좌표 순서는 `[longitude, latitude]`이다.
