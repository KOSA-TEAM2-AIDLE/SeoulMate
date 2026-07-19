import { useEffect, useRef } from 'react';
import { clearMarkers, createPlaceMarkers } from '../../services/map/markerService';

export function useMapMarkers({
  naver,
  map,
  places = [],
  onMarkerClick
}) {
  const markerItemsRef = useRef([]);

  useEffect(() => {
    if (!naver || !map || places.length === 0) {
      clearMarkers(markerItemsRef.current);
      markerItemsRef.current = [];
      return;
    }

    clearMarkers(markerItemsRef.current);

    markerItemsRef.current = createPlaceMarkers({
      naver,
      map,
      places,
      onMarkerClick,
    });

    return () => {
      clearMarkers(markerItemsRef.current);
      markerItemsRef.current = [];
    };
  }, [naver, map, places, onMarkerClick]);

  return {
    markerItemsRef
  }
}
