import { useEffect, useRef } from 'react';
import { clearMarkers, createPlaceMarkers } from '../../services/map/markerService';

export function useMapMarkers({
  kakao,
  map,
  places = [],
  onMarkerClick
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
      onMarkerClick,
    });

    return () => {
      clearMarkers(markerItemsRef.current);
      markerItemsRef.current = [];
    };
  }, [kakao, map, places, onMarkerClick]);

  return {
    markerItemsRef
  }
}