export function extractGeometryPaths(geometry) {
  return (geometry?.lane ?? []).flatMap((lane) => (lane.section ?? [])
    .map((section) => (section.graphPos ?? [])
      .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y))
      .map((point) => [point.x, point.y]))
    .filter((path) => path.length > 1));
}

export function extractGeometryPlaces(geometry) {
  return extractGeometryPaths(geometry)
    .flat()
    .map(([lng, lat]) => ({ lat, lng }));
}

const isCoordinate = (point) => Number.isFinite(point?.lat) && Number.isFinite(point?.lng);
const pointFromStep = (step, prefix) => ({ lat: step[`${prefix}Y`], lng: step[`${prefix}X`] });

export function extractTransitWalkPaths(segment) {
  if (!segment?.origin || !segment?.destination) return [];
  const transitSteps = (segment.route?.steps ?? []).filter((step) => step.trafficType !== 3 && isCoordinate(pointFromStep(step, 'start')) && isCoordinate(pointFromStep(step, 'end')));
  if (!transitSteps.length) return [];

  const paths = [];
  let previousPoint = segment.origin;
  transitSteps.forEach((step) => {
    const boardingPoint = pointFromStep(step, 'start');
    if (isCoordinate(previousPoint) && isCoordinate(boardingPoint)) paths.push([previousPoint, boardingPoint]);
    previousPoint = pointFromStep(step, 'end');
  });
  if (isCoordinate(previousPoint) && isCoordinate(segment.destination)) paths.push([previousPoint, segment.destination]);
  return paths;
}

function drawInteractiveLine({ naver, map, path, strokeStyle, strokeColor, strokeWeight, strokeOpacity, onClick }) {
  const naverPath = path.map((point) => new naver.maps.LatLng(point.lat, point.lng));
  const line = new naver.maps.Polyline({ map, path: naverPath, strokeColor, strokeWeight, strokeOpacity, strokeStyle, clickable: false, zIndex: 20 });
  const hitArea = new naver.maps.Polyline({ map, path: naverPath, strokeColor, strokeWeight: 18, strokeOpacity: 0, clickable: true, zIndex: 30 });
  naver.maps.Event.addListener(hitArea, 'mouseover', () => line.setOptions({ strokeWeight: strokeWeight + 3, strokeOpacity: 1 }));
  naver.maps.Event.addListener(hitArea, 'mouseout', () => line.setOptions({ strokeWeight, strokeOpacity }));
  naver.maps.Event.addListener(hitArea, 'click', () => onClick?.());
  return [line, hitArea];
}

export function drawTransitGeometry({ naver, map, geometry, onClick }) {
  if (!naver || !map || !geometry) return [];
  return extractGeometryPaths(geometry).flatMap((path) => {
    return drawInteractiveLine({ naver, map, path: path.map(([lng, lat]) => ({ lat, lng })), strokeColor: '#2563eb', strokeWeight: 5, strokeOpacity: 0.9, strokeStyle: 'solid', onClick });
  });
}

export function drawTransitWalkConnectors({ naver, map, segment, onClick }) {
  if (!naver || !map) return [];
  return extractTransitWalkPaths(segment).flatMap((path) => drawInteractiveLine({ naver, map, path, strokeColor: '#2563eb', strokeWeight: 3, strokeOpacity: 0.8, strokeStyle: 'shortdash', onClick }));
}

export function clearTransitGeometry(lines) { lines.forEach((line) => line.setMap(null)); }
