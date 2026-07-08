import { useState } from 'react';
import useTravelStore from '../stores/useTravelStore';
import PlaceRecommendTab from '../components/sidebar/PlaceRecommendTab.jsx';
import TravelRouteTab from '../components/sidebar/TravelRouteTab';
import { getPlaceDisplayCategory } from '../services/map/placeDisplayAdapter';

export default function PlaceSidebar() {
  const [activeTab, setActiveTab] = useState('search');
  const [activeFilter, setActiveFilter] = useState('전체');
  const [toastMessage, setToastMessage] = useState('');

  const recommendList = useTravelStore((state) => state.recommendList);

  // const filteredPlaces = recommendList.filter((place) => {
  //   if (activeFilter === '전체') return true;
  //   return place.category === activeFilter;
  // });
  const filteredPlaces = recommendList.filter((place) => {
    if (activeFilter === '전체') return true;
    return getPlaceDisplayCategory(place) === activeFilter;
  });

  const showToast = (message) => {
    setToastMessage(message);
    setTimeout(() => setToastMessage(''), 2000);
  };

  return (
      <aside className="relative flex h-full w-[380px] flex-col border border-slate-200 bg-white shadow-xl rounded-2xl overflow-hidden font-sans">

        {/* 토스트 피드백 레이어 */}
        {toastMessage && (
            <div className="absolute top-16 left-1/2 z-50 -translate-x-1/2 rounded-full bg-slate-900 px-4 py-2 text-xs font-medium text-white shadow-md animate-bounce">
              {toastMessage}
            </div>
        )}

        {/* 상단 탭 헤더 컨트롤러 */}
        <nav className="grid grid-cols-2 border-b border-slate-200 text-sm font-semibold shrink-0">
          <button
              type="button"
              onClick={() => setActiveTab('search')}
              className={`px-4 py-4 transition-all ${
                  activeTab === 'search' ? 'border-b-2 border-blue-600 text-blue-600' : 'text-slate-400 hover:text-slate-600'
              }`}
          >
            장소 추천
          </button>
          <button
              type="button"
              onClick={() => setActiveTab('route')}
              className={`px-4 py-4 transition-all ${
                  activeTab === 'route' ? 'border-b-2 border-blue-600 text-blue-600' : 'text-slate-400 hover:text-slate-600'
              }`}
          >
            내 여행 루트
          </button>
        </nav>

        {/* 내부 분기 렌더링 영역 */}
        <div className="flex-1 min-h-0 flex flex-col">
          {activeTab === 'search' ? (
              <PlaceRecommendTab
                  activeFilter={activeFilter}
                  setActiveFilter={setActiveFilter}
                  filteredPlaces={filteredPlaces}
                  showToast={showToast}
              />
          ) : (
              <TravelRouteTab
                  showToast={showToast}
              />
          )}
        </div>
      </aside>
  );
}