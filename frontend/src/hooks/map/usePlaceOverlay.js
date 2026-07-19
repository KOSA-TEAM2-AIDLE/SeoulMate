import { useEffect, useRef } from 'react';
import { clearPlaceOverlay, createPlaceOverlay } from '../../services/map/overlayService';

export function usePlaceOverlay({
  naver,
  map,
  place,
  onClose,
}) {
  const overlayRef = useRef(null);

  useEffect(() => {
    clearPlaceOverlay(overlayRef.current);
    overlayRef.current = null;

    if (!naver || !map || !place) {
      return;
    }

    overlayRef.current = createPlaceOverlay({
      naver,
      map,
      place,
      onClose,
    });

    return () => {
      clearPlaceOverlay(overlayRef.current);
      overlayRef.current = null;
    };
  }, [naver, map, place, onClose]);

  return {
    overlayRef,
  };
}
