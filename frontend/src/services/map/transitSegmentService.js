const EARTH_RADIUS_METERS = 6_371_000;
const WALKING_METERS_PER_MINUTE = 75;
export const ODSAY_MIN_DISTANCE_METERS = 700;

const toRadians = (degrees) => (degrees * Math.PI) / 180;

export function distanceMeters(origin, destination) {
  const latitudeDelta = toRadians(destination.lat - origin.lat);
  const longitudeDelta = toRadians(destination.lng - origin.lng);
  const originLatitude = toRadians(origin.lat);
  const destinationLatitude = toRadians(destination.lat);
  const haversine = Math.sin(latitudeDelta / 2) ** 2
    + Math.cos(originLatitude) * Math.cos(destinationLatitude) * Math.sin(longitudeDelta / 2) ** 2;
  return 2 * EARTH_RADIUS_METERS * Math.asin(Math.sqrt(haversine));
}

export const isWalkablePair = (meters) => meters < ODSAY_MIN_DISTANCE_METERS;

export function createWalkSegment(origin, destination) {
  const distance_meters = Math.round(distanceMeters(origin, destination));
  const duration_minutes = Math.max(1, Math.ceil(distance_meters / WALKING_METERS_PER_MINUTE));
  return {
    origin,
    destination,
    route: {
      mode: 'walk',
      distance_meters,
      duration_minutes,
      walking_minutes: duration_minutes,
      transfers: 0,
      fare: 0,
      steps: [],
      map_object: null,
    },
  };
}

export function createTransitSegment(origin, destination, route) {
  return { origin, destination, route: { ...route, mode: 'transit' } };
}

export function createUnavailableSegment(origin, destination, error) {
  return {
    origin,
    destination,
    route: {
      mode: 'unavailable',
      duration_minutes: null,
      walking_minutes: null,
      transfers: null,
      fare: null,
      steps: [],
      map_object: null,
      error: error instanceof Error ? error.message : String(error),
    },
  };
}
