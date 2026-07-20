import { useCallback, useEffect, useMemo } from 'react';
import { useNaverMap } from '../../hooks/map/useNaverMap';
import { useMapMarkers } from '../../hooks/map/useMapMarkers';
import { usePlaceOverlay } from '../../hooks/map/usePlaceOverlay';
import { useRoutePolyline } from '../../hooks/map/useRoutePolyline';
import { useTransitGeometryLayer } from '../../hooks/map/useTransitGeometryLayer';
import { getRouteViewportPlaces } from '../../services/map/routeSegmentNavigation';
import useTravelStore from '../../stores/useTravelStore';

const SEOUL_CENTER = { lat: 37.5665, lng: 126.978 };

export default function NaverMap({ places = [], segments = [], selectedSegment, isSegmentSelected = false, selectedSegmentIndex, hiddenSegmentIndex, onSegmentSelect, transitGeometry, language }) {
  const setSelectedPlace = useTravelStore((state) => state.setSelectedPlace);
  const selectedPlace = useTravelStore((state) => state.selectedPlace);
  const clearSelectedPlace = useTravelStore((state) => state.clearSelectedPlace);
  const { naver, map, mapContainerRef, isLoading, isMapReady, error, fitPlaces } = useNaverMap({ center: SEOUL_CENTER, zoom: 12, language });
  const handleGeometryClick = useCallback(() => onSegmentSelect?.(selectedSegmentIndex), [onSegmentSelect, selectedSegmentIndex]);
  const viewportPlaces = useMemo(
    () => getRouteViewportPlaces(places, selectedSegment, isSegmentSelected),
    [places, selectedSegment, isSegmentSelected],
  );
  useMapMarkers({ naver, map, places, onMarkerClick: setSelectedPlace });
  usePlaceOverlay({ naver, map, place: selectedPlace, onClose: clearSelectedPlace });
  useRoutePolyline({ naver, map, places, segments, hiddenSegmentIndex, selectedSegmentIndex, onSegmentSelect });
  useTransitGeometryLayer({ naver, map, geometry: transitGeometry, segment: selectedSegment, onClick: handleGeometryClick });

  useEffect(() => {
    if (map) fitPlaces(viewportPlaces);
  }, [map, viewportPlaces, fitPlaces]);

  if (error) {
    return <div className="flex h-full min-h-[460px] flex-col items-center justify-center gap-2 bg-slate-100 px-6 text-center text-sm font-semibold text-red-500"><span>지도를 불러오지 못했습니다.</span><span className="max-w-lg text-xs font-normal text-slate-600">{error.message}</span></div>;
  }

  return (
    <div className="relative h-full min-h-[460px] w-full">
      {isLoading && <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-100 text-sm font-semibold text-slate-500">지도를 불러오는 중...</div>}
      <div ref={mapContainerRef} className="h-full min-h-[460px] w-full" />
      {!isLoading && !isMapReady && <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-100 text-sm font-semibold text-slate-500">지도 준비 중...</div>}
    </div>
  );
}
