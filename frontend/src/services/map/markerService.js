/* 임시 마커 색상 */
const MARKER_IMAGE_BY_TYPE = {
  cafe: {
    color: '#2563eb',
  },
  restaurant: {
    color: '#dc2626',
  },
  accommodation: {
    color: '#9333ea',
  },
  event: {
    color: '#9333ea',
  },
  'storage-locker': {
    color: '#f59e0b',
  },
};
/* 임시 마커 이미지 */
function createMarkerContent(type, order) {
  const markerStyle = MARKER_IMAGE_BY_TYPE[type] ?? {
    color: '#475569',
  };

  const isIcon = type === 'accommodation';
  const padding = isIcon ? '0' : '0 8px';

  const content = isIcon
    ? `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="white"><path d="M7 13c1.66 0 3-1.34 3-3S8.66 7 7 7s-3 1.34-3 3 1.34 3 3 3zm12-6h-8v7H3V5H1v15h2v-3h18v3h2v-9c0-2.21-1.79-4-4-4z"/></svg>`
    : order;

  return `<div style="display:flex;align-items:center;justify-content:center;min-width:34px;height:34px;padding:${padding};border:3px solid white;border-radius:10px;background:${markerStyle.color};box-shadow:0 4px 10px rgba(15,23,42,.25);color:white;font-size:14px;font-weight:800">${content}</div>`;
}

export function markerType(place) {
  const category = String(place.category ?? '').toLowerCase();
  if (category.includes('카페') || category.includes('cafe')) return 'cafe';
  if (category.includes('맛집') || category.includes('restaurant')) return 'restaurant';
  if (category.includes('숙소') || category.includes('hotel') || category.includes('accommodation')) return 'accommodation';
  if (category.includes('보관') || category.includes('luggage')) return 'storage-locker';
  return place.type;
}

export function createPlaceMarker({ naver, map, place, order, onClick }) {
  const position = new naver.maps.LatLng(place.lat, place.lng);

  const marker = new naver.maps.Marker({
    map,
    position,
    icon: { content: createMarkerContent(markerType(place), order), anchor: new naver.maps.Point(17, 17) },
    title: place.name,
  });

  if (onClick) naver.maps.Event.addListener(marker, 'click', () => onClick(place));

  return marker;
}

export function createPlaceMarkers({ naver, map, places, onMarkerClick }) {
  return places.map((place, index) => ({
    place,
    marker: createPlaceMarker({
      naver,
      map,
      place,
      order: index + 1,
      onClick: onMarkerClick,
    }),
  })); // Marker - place 구조를 통해 어느 마커가 어느 place 인지 추적가능 하기 위함
}

export function clearMarkers(markerItems) {
  markerItems.forEach(({ marker }) => {
    marker.setMap(null);
  });
}
