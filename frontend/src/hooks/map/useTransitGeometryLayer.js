import { useEffect, useRef } from 'react';
import { drawTransitGeometry, drawTransitWalkConnectors, clearTransitGeometry } from '../../services/map/transitGeometryService';

export function useTransitGeometryLayer({ naver, map, geometry, segment, onClick }) {
  const linesRef = useRef([]);
  useEffect(() => {
    const lines = [
      ...drawTransitGeometry({ naver, map, geometry, onClick }),
      ...drawTransitWalkConnectors({ naver, map, segment, onClick }),
    ];
    linesRef.current = lines;
    return () => {
      clearTransitGeometry(lines);
      if (linesRef.current === lines) linesRef.current = [];
    };
  }, [naver, map, geometry, segment, onClick]);
}
