import { useEffect, useRef } from 'react';
import { clearMarkers, createPlaceMarkers } from '../../services/map/markerService';

export function useMapMarkers({
  kakao,
  map,
  places = [],
}) {
  const markerItemsRef = useRef([]);

  useEffect(() => {
    if (!kakao || !map || places.length === 0) {
      clearMarkers(markerItemsRef.current);
      markerItemsRef.current = [];
      return;
    }

    clearMarkers(markerItemsRef.current);

    markerItemsRef.current = createPlaceMarkers({
      kakao,
      map,
      places,
    });

    return () => {
      clearMarkers(markerItemsRef.current);
      markerItemsRef.current = [];
    };
  }, [kakao, map, places]);

  return {
    markerItemsRef
  }
}