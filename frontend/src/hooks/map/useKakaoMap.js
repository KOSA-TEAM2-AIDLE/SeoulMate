import { useEffect, useRef, useState } from 'react';
import { useKakaoMapLoader } from './useKakaoMapLoader';

const DEFAULT_CENTER = {
  lat: 37.5665,
  lng: 126.978,
};

const DEFAULT_LEVEL = 7;

export function useKakaoMap({
  center = DEFAULT_CENTER,
  level = DEFAULT_LEVEL,
} = {}) {
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);

  const [isMapReady, setIsMapReady] = useState(false);
  const [ map, setMap ] = useState(null);

  const {
    kakao,
    isLoading,
    isLoaded,
    error,
  } = useKakaoMapLoader();

  useEffect(() => {
    if (!isLoaded || !kakao || !mapContainerRef.current) {
      return;
    }

    const mapCenter = new kakao.maps.LatLng(center.lat, center.lng);

    if (!mapRef.current) {
      const options = {
        center: mapCenter,
        level,
      };

      const createMap = new kakao.maps.Map(mapContainerRef.current, options);
      mapRef.current = createMap
      setMap(createMap)
      setIsMapReady(true);

      return;
    }

    mapRef.current.setCenter(mapCenter);
    mapRef.current.setLevel(level);
  }, [kakao, isLoaded, center.lat, center.lng, level]);

  return {
        kakao,
        mapContainerRef,
        map,
        isMapReady,
        isLoading,
        isLoaded,
        error,
    };
}