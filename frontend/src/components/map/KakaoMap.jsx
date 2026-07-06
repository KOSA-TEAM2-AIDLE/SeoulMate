import { useKakaoMap } from '../../hooks/map/useKakaoMap';

const SEOUL_CENTER = {
  lat: 37.5665,
  lng: 126.978,
};

export default function KakaoMap() {
  const {
    mapContainerRef,
    isLoading,
    isMapReady,
    error,
  } = useKakaoMap({
    center: SEOUL_CENTER,
    level: 7,
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