export function createRoutePolyline({ naver, map, places, segments = [], hiddenSegmentIndex = null, selectedSegmentIndex = null, onClick }) {
  return places.slice(0, -1).flatMap((place, index) => {
    if (index === hiddenSegmentIndex) return [];
    const mode = segments[index]?.route?.mode ?? 'walk';
    const isSelected = index === selectedSegmentIndex;
    const baseOpacity = isSelected ? 1 : (mode === 'transit' ? 0.45 : 0.75);
    const baseWeight = isSelected ? 6 : 3;
    const path = [
      new naver.maps.LatLng(place.lat, place.lng),
      new naver.maps.LatLng(places[index + 1].lat, places[index + 1].lng),
    ];
    const line = new naver.maps.Polyline({
      map,
      path,
      strokeWeight: baseWeight,
      strokeColor: mode === 'unavailable' ? '#94a3b8' : '#2563eb',
      strokeOpacity: baseOpacity,
      strokeStyle: mode === 'transit' ? 'solid' : 'shortdash',
      clickable: false,
    });
    const hitArea = new naver.maps.Polyline({
      map,
      path,
      strokeWeight: 18,
      strokeColor: '#2563eb',
      strokeOpacity: 0,
      clickable: true,
      zIndex: 30,
    });
    naver.maps.Event.addListener(hitArea, 'mouseover', () => line.setOptions({ strokeWeight: baseWeight + 3, strokeOpacity: 1 }));
    naver.maps.Event.addListener(hitArea, 'mouseout', () => line.setOptions({ strokeWeight: baseWeight, strokeOpacity: baseOpacity }));
    naver.maps.Event.addListener(hitArea, 'click', () => onClick?.(index));
    return [line, hitArea];
  });
}

export function clearPolyline(polyline) {
  (Array.isArray(polyline) ? polyline : [polyline]).filter(Boolean).forEach((line) => line.setMap(null));
}
