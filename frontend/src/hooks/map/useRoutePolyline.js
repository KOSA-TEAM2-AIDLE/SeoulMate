import { useEffect, useRef } from 'react';
import { clearPolyline, createRoutePolyline } from '../../services/map/polylineService';

export function useRoutePolyline({
  naver,
  map,
  places = [],
  segments = [],
  enabled = true,
  hiddenSegmentIndex = null,
  selectedSegmentIndex = null,
  onSegmentSelect,
}) {
  const polylineRef = useRef(null);

  useEffect(() => {
    clearPolyline(polylineRef.current);
    polylineRef.current = null;

    if (!enabled || !naver || !map || places.length < 2) {
      return;
    }

    polylineRef.current = createRoutePolyline({
      naver,
      map,
      places,
      segments,
      hiddenSegmentIndex,
      selectedSegmentIndex,
      onClick: onSegmentSelect,
    });

    const lines = polylineRef.current;
    return () => {
      clearPolyline(lines);
      if (polylineRef.current === lines) polylineRef.current = null;
    };
  }, [naver, map, places, segments, enabled, hiddenSegmentIndex, selectedSegmentIndex, onSegmentSelect]);
}
