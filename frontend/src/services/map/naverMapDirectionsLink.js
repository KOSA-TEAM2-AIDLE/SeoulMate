const NAVER_MAP_WEB_DIRECTIONS_URL = 'https://map.naver.com/p/directions/';
const WEB_MERCATOR_ORIGIN_SHIFT = 20037508.342789244;

function getPlaceLabel(place) {
  return [place?.name, place?.address].filter(Boolean).join(' · ');
}

function getWebMercatorCoordinate(place) {
  if (!Number.isFinite(place?.lat) || !Number.isFinite(place?.lng)) return null;
  const x = place.lng * WEB_MERCATOR_ORIGIN_SHIFT / 180;
  const y = Math.log(Math.tan((90 + place.lat) * Math.PI / 360)) / (Math.PI / 180) * WEB_MERCATOR_ORIGIN_SHIFT / 180;
  return `${x},${y}`;
}

function createNaverWebDirectionsUrl(origin, destination, mode) {
  const originCoordinate = getWebMercatorCoordinate(origin);
  const destinationCoordinate = getWebMercatorCoordinate(destination);
  if (!originCoordinate || !destinationCoordinate) return NAVER_MAP_WEB_DIRECTIONS_URL;
  const routeMode = mode === 'walk' ? 'walk' : 'transit';
  const originPlace = `${originCoordinate},${encodeURIComponent(getPlaceLabel(origin))},,ADDRESS_POI`;
  const destinationPlace = `${destinationCoordinate},${encodeURIComponent(getPlaceLabel(destination))},,ADDRESS_POI`;
  return `${NAVER_MAP_WEB_DIRECTIONS_URL}${originPlace}/${destinationPlace}/-/${routeMode}?c=11.00,0,0,0,dh`;
}

export function createNaverRouteAppUrl(origin, destination, appName, mode = 'public') {
  const params = new URLSearchParams({
    slat: String(origin.lat),
    slng: String(origin.lng),
    sname: getPlaceLabel(origin),
    dlat: String(destination.lat),
    dlng: String(destination.lng),
    dname: getPlaceLabel(destination),
    appname: appName,
  });
  const routeMode = mode === 'walk' ? 'walk' : 'public';
  return `nmap://route/${routeMode}?${params}`;
}

export function createNaverTransitAppUrl(origin, destination, appName) {
  return createNaverRouteAppUrl(origin, destination, appName, 'public');
}

export function getNaverMapDirectionsUrl(origin, destination, appName, userAgent = '', mode = 'public') {
  if (/Android|iPhone|iPad|iPod/i.test(userAgent)) {
    return createNaverRouteAppUrl(origin, destination, appName, mode);
  }
  return createNaverWebDirectionsUrl(origin, destination, mode);
}
