import { useEffect, useState } from 'react';
import KakaoMap from '../components/map/KakaoMap';
import { getMapPlaces } from '../services/map/placeApi';
import useTravelStore from '../stores/useTravelStore';

export default function MapWorkspace() {
  // const [places, setPlaces] = useState([]);
  const [isPlaceLoading, setIsPlaceLoading] = useState(true);
  const [placeError, setPlaceError] = useState(null);

  const currentDay = useTravelStore((state) => state.day);
  const travelPath = useTravelStore((state) => state.travelPath);

  const setAllPlaces = useTravelStore((state) => state.setAllPlaces);
  const setRecommendList = useTravelStore((state) => state.setRecommendList);

  const routePlaces = travelPath[currentDay] || [];

  useEffect(() => {
    let isMounted = true;

    async function loadPlaces() {
      try {
        setIsPlaceLoading(true);
        setPlaceError(null);

        const mapPlaces = await getMapPlaces();

        if (isMounted) {
          // setPlaces(mapPlaces);
          setAllPlaces(mapPlaces);
          setRecommendList(mapPlaces);
        }
      } catch (error) {
        if (isMounted) {
          setPlaceError(error);
        }
      } finally {
        if (isMounted) {
          setIsPlaceLoading(false);
        }
      }
    }

    loadPlaces();

    return () => {
      isMounted = false;
    };
  }, [setAllPlaces, setRecommendList]);

  return (
    <section className="relative min-h-[460px] overflow-hidden bg-blue-50">
      <KakaoMap places={routePlaces} />

      {isPlaceLoading && (
        <div className="absolute left-4 top-4 rounded-lg bg-white px-3 py-2 text-sm font-semibold text-slate-500 shadow">
          장소 데이터를 불러오는 중...
        </div>
      )}

      {placeError && (
        <div className="absolute left-4 top-4 rounded-lg bg-white px-3 py-2 text-sm font-semibold text-red-500 shadow">
          장소 데이터를 불러오지 못했습니다.
        </div>
      )}

      <div className="absolute bottom-5 left-1/2 w-[min(520px,calc(100%-40px))] -translate-x-1/2 rounded-xl border border-slate-200 bg-white p-4 shadow-lg">
        <p className="text-sm font-semibold text-blue-600">선택된 장소 정보 카드</p>
        <p className="mt-1 text-sm text-slate-500">
          현재 표시 중인 장소 수: {routePlaces.length}
        </p>
      </div>
    </section>
  );
}