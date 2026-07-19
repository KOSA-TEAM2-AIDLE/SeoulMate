import { useEffect, useState } from 'react';
import { fetchTransitRoute } from '../../api/transitRoutes';
import {
  createTransitSegment,
  createUnavailableSegment,
  createWalkSegment,
  distanceMeters,
  isWalkablePair,
} from '../../services/map/transitSegmentService';

export function useTransitRoutes(places, language) {
  const [segments, setSegments] = useState([]);
  const routeKey = places.map((place) => `${place.id}:${place.lat}:${place.lng}`).join('|');
  useEffect(() => {
    let alive = true;
    const pairs = places.slice(0, -1)
      .map((origin, index) => [origin, places[index + 1]])
      .filter(([origin, destination]) => Number.isFinite(origin.lat) && Number.isFinite(origin.lng) && Number.isFinite(destination.lat) && Number.isFinite(destination.lng));

    Promise.all(pairs.map(async ([origin, destination]) => {
      if (isWalkablePair(distanceMeters(origin, destination))) {
        return createWalkSegment(origin, destination);
      }

      try {
        return createTransitSegment(origin, destination, await fetchTransitRoute(origin, destination, language));
      } catch (error) {
        return createUnavailableSegment(origin, destination, error);
      }
    })).then((items) => {
      if (alive) setSegments(items);
    });
    return () => { alive = false; };
  }, [routeKey, language]);
  return segments;
}
