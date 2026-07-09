import { useKakaoMap } from '../../hooks/map/useKakaoMap';
import { useMapMarkers } from '../../hooks/map/useMapMarkers';
import { usePlaceOverlay } from '../../hooks/map/usePlaceOverlay';
import { useRoutePolyline } from '../../hooks/map/useRoutePolyline';
import useTravelStore from '../../stores/useTravelStore';

const SEOUL_CENTER = {
  lat: 37.5665,
  lng: 126.978,
};



export default function KakaoMap({ places = [], showRouteLine = true }) {
  const setSelectedPlace = useTravelStore((state) => state.setSelectedPlace);
  const selectedPlace = useTravelStore((state) => state.selectedPlace);
  const clearSelectedPlace = useTravelStore((state) => state.clearSelectedPlace);
  
  const {
    kakao,
    map,
    mapContainerRef,
    isLoading,
    isMapReady,
    error,
  } = useKakaoMap({
    center: SEOUL_CENTER,
    level: 7,
  });

  useMapMarkers({
    kakao,
    map,
    places,
    onMarkerClick: setSelectedPlace,
  });

  usePlaceOverlay({
    kakao,
    map,
    place: selectedPlace,
    onClose: clearSelectedPlace,
  });

  useRoutePolyline({
    kakao,
    map,
    places,
    enabled: showRouteLine,
  });


  if (error) {
    return (
      <div className="flex h-full min-h-[460px] items-center justify-center bg-slate-100 text-sm font-semibold text-red-500">
        지도를 불러오지 못했습니다.
      </div>
    );
  }

  return (
    <div className="relative h-full min-h-[460px] w-full">
      {isLoading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-100 text-sm font-semibold text-slate-500">
          지도를 불러오는 중...
        </div>
      )}

      <div ref={mapContainerRef} className="h-full min-h-[460px] w-full" />

      {!isLoading && !isMapReady && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-100 text-sm font-semibold text-slate-500">
          지도 준비 중...
        </div>
      )}
    </div>
  );
}
