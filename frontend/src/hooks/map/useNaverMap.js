import { useCallback, useEffect, useRef, useState } from 'react';

import { useNaverMapLoader } from './useNaverMapLoader';

const DEFAULT_CENTER = { lat: 37.5665, lng: 126.978 };

export function useNaverMap({ center = DEFAULT_CENTER, zoom = 12, language = 'en' } = {}) {
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);
  const [map, setMap] = useState(null);
  const [isMapReady, setIsMapReady] = useState(false);
  const { naver, isLoading, isLoaded, error } = useNaverMapLoader(language);

  const fitPlaces = useCallback((places) => {
    if (!naver || !mapRef.current) return;
    const validPlaces = places.filter((place) => Number.isFinite(place?.lat) && Number.isFinite(place?.lng));
    if (!validPlaces.length) return;
    if (validPlaces.length === 1) {
      mapRef.current.setCenter(new naver.maps.LatLng(validPlaces[0].lat, validPlaces[0].lng));
      mapRef.current.setZoom(15);
      return;
    }
    const bounds = new naver.maps.LatLngBounds();
    validPlaces.forEach((place) => bounds.extend(new naver.maps.LatLng(place.lat, place.lng)));
    mapRef.current.fitBounds(bounds, { top: 80, right: 80, bottom: 200, left: 80 });
  }, [naver]);

  useEffect(() => {
    if (!isLoaded || !naver || !mapContainerRef.current) return;

    const position = new naver.maps.LatLng(center.lat, center.lng);
    if (!mapRef.current) {
      const instance = new naver.maps.Map(mapContainerRef.current, { center: position, zoom });
      mapRef.current = instance;
      setMap(instance);
      setIsMapReady(true);
      return;
    }
    mapRef.current.setCenter(position);
    mapRef.current.setZoom(zoom);
  }, [naver, isLoaded, center.lat, center.lng, zoom]);

  return { naver, map, mapContainerRef, isLoading, isMapReady, error, fitPlaces };
}
