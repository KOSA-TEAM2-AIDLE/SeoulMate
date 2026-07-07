/* 임시 마커 색상 */
const MARKER_IMAGE_BY_TYPE = {
  cafe: {
    color: '#2563eb',
  },
  restaurant: {
    color: '#dc2626',
  },
  accommodation: {
    color: '#16a34a',
  },
  event: {
    color: '#9333ea',
  },
  'storage-locker': {
    color: '#f59e0b',
  },
};
/* 임시 마커 이미지 */
function createMarkerImage(kakao, type) {
  const markerStyle = MARKER_IMAGE_BY_TYPE[type] ?? {
    color: '#475569',
  };

  const svg = `
    <svg width="36" height="42" viewBox="0 0 36 42" xmlns="http://www.w3.org/2000/svg">
      <path d="M18 0C8.6 0 1 7.6 1 17c0 12.8 17 25 17 25s17-12.2 17-25C35 7.6 27.4 0 18 0Z" fill="${markerStyle.color}"/>
      <circle cx="18" cy="17" r="6" fill="white"/>
    </svg>
  `;

  const markerImageUrl = `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
  const imageSize = new kakao.maps.Size(36, 42);
  const imageOption = {
    offset: new kakao.maps.Point(18, 42),
  };

  return new kakao.maps.MarkerImage(markerImageUrl, imageSize, imageOption);
}

export function createPlaceMarker({ kakao, map, place }) {
  const position = new kakao.maps.LatLng(place.lat, place.lng);
  const image = createMarkerImage(kakao, place.type);

  const marker = new kakao.maps.Marker({
    map,
    position,
    image,
    title: place.name,
  });

  return marker;
}

export function createPlaceMarkers({ kakao, map, places }) {
  return places.map((place) => ({
    place,
    marker: createPlaceMarker({
      kakao,
      map,
      place,
    }),
  })); // Marker - place 구조를 통해 어느 마커가 어느 place 인지 추적가능 하기 위함
}

export function clearMarkers(markerItems) {
  markerItems.forEach(({ marker }) => {
    marker.setMap(null);
  });
}