import { useState } from 'react';
import PlaceRecommendTab from '../components/sidebar/PlaceRecommendTab.jsx';
import TravelRouteTab from '../components/sidebar/TravelRouteTab';

const INTEGRATED_PLACE_ITEMS = [
  {
    id: "ACCO001",
    name: "파크 하얏트 서울",
    category: "숙소",
    subCategory: "럭셔리",
    address: "서울 강남구 테헤란로 606",
    rating: "4.7",
    reviews: "1,842",
    time: "15:00 (체크인)",
    image: "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=150&q=80"
  },
  {
    id: "ACCO002",
    name: "롯데호텔 서울",
    category: "숙소",
    subCategory: "럭셔리",
    address: "서울 중구 을지로 30",
    rating: "4.6",
    reviews: "3,124",
    time: "15:00 (체크인)",
    image: "https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=150&q=80"
  },
  {
    id: "CAFE002",
    name: "블루보틀 삼청",
    category: "카페",
    subCategory: "스페셜티 커피",
    address: "서울 종로구 삼청로 87",
    rating: "4.5",
    reviews: "120",
    time: "14:00 - 15:00",
    image: "https://images.unsplash.com/photo-1509042239860-f550ce710b93?auto=format&fit=crop&w=150&q=80"
  },
  {
    id: "CAFE003",
    name: "어니언 성수",
    category: "카페",
    subCategory: "베이커리 카페",
    address: "서울 성동구 아차산로9길 8",
    rating: "4.7",
    reviews: "1,450",
    time: "16:30 - 17:30",
    image: "https://images.unsplash.com/photo-1498804103079-a6351b050096?auto=format&fit=crop&w=150&q=80"
  },
  {
    id: "EVT006",
    name: "경복궁 야간개장",
    category: "명소",
    subCategory: "궁궐/야간",
    address: "서울 종로구 사직로 161",
    rating: "4.9",
    reviews: "2,840",
    time: "19:30 - 21:00",
    image: "https://images.unsplash.com/photo-1578469550956-0e16b69c6a3d?auto=format&fit=crop&w=150&q=80"
  },
  {
    id: "REST002",
    name: "광장시장 박가네 빈대떡",
    category: "맛집",
    subCategory: "한식/분식",
    address: "서울 종로구 창경궁로 88",
    rating: "4.6",
    reviews: "934",
    time: "12:00 - 13:00",
    image: "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=150&q=80"
  },
  {
    id: "LOCKER003",
    name: "경복궁역 물품보관소",
    category: "보관소",
    subCategory: "지하철역 내",
    address: "서울 종로구 사직로 130",
    rating: "4.4",
    reviews: "45",
    time: "09:00 (짐 보관)",
    image: "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=150&q=80"
  }
];

const INITIAL_ROUTES = {
  1: [INTEGRATED_PLACE_ITEMS[6], INTEGRATED_PLACE_ITEMS[4], INTEGRATED_PLACE_ITEMS[2]],
  2: [INTEGRATED_PLACE_ITEMS[5], INTEGRATED_PLACE_ITEMS[3]],
  3: [INTEGRATED_PLACE_ITEMS[0]],
};

export default function PlaceSidebar() {
  const [activeTab, setActiveTab] = useState('search');
  const [activeFilter, setActiveFilter] = useState('전체');
  const [selectedDay, setSelectedDay] = useState(1);
  const [routes, setRoutes] = useState(INITIAL_ROUTES);
  const [days] = useState([1, 2, 3]);
  const [toastMessage, setToastMessage] = useState('');

  const filteredPlaces = INTEGRATED_PLACE_ITEMS.filter((place) => {
    if (activeFilter === '전체') return true;
    return place.category === activeFilter;
  });

  const handleDeletePlace = (id) => {
    const updatedDayList = routes[selectedDay].filter((place) => place.id !== id);
    setRoutes({ ...routes, [selectedDay]: updatedDayList });
  };

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
                  days={days}
                  selectedDay={selectedDay}
                  setSelectedDay={setSelectedDay}
                  currentRoute={routes[selectedDay]}
                  handleDeletePlace={handleDeletePlace}
                  showToast={showToast}
              />
          )}
        </div>
      </aside>
  );
}