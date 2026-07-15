import { useEffect, useRef } from 'react';
import { clearPlaceOverlay, createPlaceOverlay } from '../../services/map/overlayService';

export function usePlaceOverlay({
  kakao,
  map,
  place,
  onClose,
}) {
  const overlayRef = useRef(null);

  useEffect(() => {
    clearPlaceOverlay(overlayRef.current);
    overlayRef.current = null;

    if (!kakao || !map || !place) {
      return;
    }

    overlayRef.current = createPlaceOverlay({
      kakao,
      map,
      place,
      onClose,
    });

    return () => {
      clearPlaceOverlay(overlayRef.current);
      overlayRef.current = null;
    };
  }, [kakao, map, place, onClose]);

  return {
    overlayRef,
  };
}
