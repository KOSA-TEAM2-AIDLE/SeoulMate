export function createRoutePolyline({ kakao, map, places }) {
  const path = places.map((place) => (
    new kakao.maps.LatLng(place.lat, place.lng)
  ));

  return new kakao.maps.Polyline({
    map,
    path,
    strokeWeight: 4,
    strokeColor: '#2563eb',
    strokeOpacity: 0.85,
    strokeStyle: 'solid',
  });
}

export function clearPolyline(polyline) {
  if (polyline) {
    polyline.setMap(null);
  }
}
