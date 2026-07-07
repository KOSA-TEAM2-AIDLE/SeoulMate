import { useEffect, useRef } from 'react';
import { clearPolyline, createRoutePolyline } from '../../services/map/polylineService';

export function useRoutePolyline({
  kakao,
  map,
  places = [],
  enabled = true,
}) {
  const polylineRef = useRef(null);

  useEffect(() => {
    clearPolyline(polylineRef.current);
    polylineRef.current = null;

    if (!enabled || !kakao || !map || places.length < 2) {
      return;
    }

    polylineRef.current = createRoutePolyline({
      kakao,
      map,
      places,
    });

    return () => {
      clearPolyline(polylineRef.current);
      polylineRef.current = null;
    };
  }, [kakao, map, places, enabled]);
}
