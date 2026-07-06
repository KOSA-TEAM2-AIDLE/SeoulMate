import { useState } from 'react';

// 1. 공통 인터페이스 규격으로 가공된 마스터 데이터셋
const INTEGRATED_PLACE_ITEMS = [
  {
    id: "ACCO001",
    name: "파크 하얏트 서울",
    category: "숙소",
    subCategory: "럭셔리",
    desc: "서울 강남구 테헤란로 606",
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
    desc: "서울 중구 을지로 30",
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
    desc: "한옥 외관을 살린 인테리어의 전통과 현대의 조화",
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
    desc: "옛 군복 공장을 개조한 성수동 대표 베이커리",
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
    desc: "봄·가을 한정 경복궁 야간 특별 관람 프로그램",
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
    desc: "광장시장에서 3대째 이어온 빈대떡 노포 명가",
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
    desc: "3호선 경복궁역 5번 출구 내 역내 보관소",
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

const PLACE_FILTERS = ['전체', '명소', '맛집', '카페', '숙소', '보관소'];

export default function PlaceSidebar() {
  const [activeTab, setActiveTab] = useState('search');
  const [activeFilter, setActiveFilter] = useState('전체');
  const [selectedDay, setSelectedDay] = useState(1);
  const [routes, setRoutes] = useState(INITIAL_ROUTES);
  const [days] = useState([1, 2, 3]); // fixed 고정 일정을 위해 setDays 제거
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

        {/* 토스트 메시지 */}
        {toastMessage && (
            <div className="absolute top-16 left-1/2 z-50 -translate-x-1/2 rounded-full bg-slate-900 px-4 py-2 text-xs font-medium text-white shadow-md animate-bounce">
              {toastMessage}
            </div>
        )}

        {/* 상단 메인 탭바 */}
        <nav className="grid grid-cols-2 border-b border-slate-200 text-sm font-semibold shrink-0">
          <button
              type="button"
              onClick={() => setActiveTab('search')}
              className={`px-4 py-4 transition-all ${
                  activeTab === 'search' ? 'border-b-2 border-blue-600 text-blue-600' : 'text-slate-400 hover:text-slate-600'
              }`}
          >
            장소 검색
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

        {/* 내부 콘텐츠 컨테이너 */}
        <div className="flex-1 min-h-0 flex flex-col">
          {activeTab === 'search' ? (
              /* [1] 장소 검색 화면 */
              <div className="flex-1 flex flex-col min-h-0">

                {/* 고정 필터 바 영역 */}
                <div className="pt-5 pb-3 space-y-4 shrink-0 border-b border-slate-50">

                  {/* 카테고리 필터 스크롤 바 */}
                  <div className="flex gap-2 overflow-x-auto pb-1 px-5 scrollbar-hide">
                    {PLACE_FILTERS.map((filter) => (
                        <button
                            key={filter}
                            type="button"
                            onClick={() => setActiveFilter(filter)}
                            className={`rounded-full border px-3.5 py-1 text-sm font-medium shrink-0 transition-colors ${
                                activeFilter === filter ? 'border-blue-600 bg-blue-600 text-white' : 'border-slate-200 text-slate-600 bg-white hover:bg-slate-50'
                            }`}
                        >
                          {filter}
                        </button>
                    ))}
                  </div>

                  {/* 결과 카운트 안내 헤더 */}
                  <div className="flex items-center justify-between pt-1 px-5">
                    <h2 className="text-base font-bold text-slate-800">검색 결과</h2>
                    <span className="text-sm text-slate-500">{filteredPlaces.length}개 발견</span>
                  </div>
                </div>

                {/* 검색결과 리스트 영역 */}
                <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3 min-h-0 bg-slate-50/40">
                  {filteredPlaces.length > 0 ? (
                      filteredPlaces.map((place) => (
                          <article key={place.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:border-slate-300 transition-all cursor-pointer group">
                            <div className="flex gap-3">
                              <div className="size-16 shrink-0 overflow-hidden rounded-lg border border-slate-100 bg-slate-50">
                                <img src={place.image} alt={place.name} className="h-full w-full object-cover group-hover:scale-105 transition-transform duration-200" />
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <h3 className="font-bold text-slate-800 truncate text-base flex-1">{place.name}</h3>
                                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0 whitespace-nowrap ${
                                      place.category === '카페' ? 'text-orange-500 bg-orange-50' :
                                          place.category === '맛집' ? 'text-green-500 bg-green-50' :
                                              place.category === '숙소' ? 'text-purple-500 bg-purple-50' :
                                                  place.category === '보관소' ? 'text-cyan-500 bg-cyan-50' : 'text-red-500 bg-red-50'
                                  }`}>
                            {place.subCategory}
                          </span>
                                </div>
                                <p className="mt-1 text-sm text-slate-400 truncate">{place.desc}</p>
                                <p className="mt-1.5 text-sm text-amber-500 font-semibold">★ {place.rating}</p>
                              </div>
                            </div>
                          </article>
                      ))
                  ) : (
                      <div className="text-center py-12 border-2 border-dashed border-slate-200 rounded-2xl text-slate-400 text-sm bg-white">
                        해당 카테고리의 결과가 존재하지 않습니다.
                      </div>
                  )}
                </div>
              </div>
          ) : (
              /* [2] 내 여행 루트 화면 */
              <div className="flex-1 flex flex-col min-h-0 p-5 space-y-6">
                <div className="flex items-center justify-between shrink-0">
                  <h2 className="text-2xl font-bold text-slate-900 tracking-tight">내 여행 루트</h2>
                  <div className="flex gap-2">
                    <button type="button" onClick={() => showToast('여행 루트가 저장되었습니다.')} className="flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-3.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-all shadow-sm">
                      저장
                    </button>
                    <button type="button" onClick={() => showToast('공유 링크가 복사되었습니다.')} className="flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-3.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-all shadow-sm">
                      공유
                    </button>
                  </div>
                </div>

                {/* Day 탭 목록 (💡 플러스 버튼 아이콘 제거 및 레이아웃 정리) */}
                <div className="flex flex-wrap items-center gap-2 shrink-0">
                  {days.map((day) => (
                      <button
                          key={day}
                          type="button"
                          onClick={() => setSelectedDay(day)}
                          className={`rounded-full px-5 py-2.5 text-sm font-semibold transition-all shadow-sm ${
                              selectedDay === day ? 'bg-blue-600 text-white border border-blue-600' : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
                          }`}
                      >
                        Day {day}
                      </button>
                  ))}
                </div>

                {/* 여행 루트 카드 리스트 */}
                <div className="flex-1 overflow-y-auto space-y-4 min-h-0 pr-1">
                  {routes[selectedDay] && routes[selectedDay].length > 0 ? (
                      routes[selectedDay].map((place, index) => (
                          <article key={place.id} className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm hover:shadow-md transition-all duration-200">

                            <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold text-white shadow-sm">
                              {index + 1}
                            </div>

                            <div className="size-16 shrink-0 overflow-hidden rounded-xl border border-slate-100 bg-slate-50 shadow-inner">
                              <img src={place.image} alt={place.name} className="h-full w-full object-cover" />
                            </div>

                            <div className="flex-1 min-w-0 flex flex-col justify-center">
                              <div className="flex items-center justify-between gap-2">
                                <h3 className="font-bold text-slate-900 truncate tracking-tight text-base flex-1">
                                  {place.name}
                                </h3>

                                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded whitespace-nowrap shrink-0 ${
                                    place.category === '카페' ? 'text-orange-500 bg-orange-50' :
                                        place.category === '맛집' ? 'text-green-500 bg-green-50' :
                                            place.category === '숙소' ? 'text-purple-500 bg-purple-50' :
                                                place.category === '보관소' ? 'text-cyan-500 bg-cyan-50' : 'text-red-500 bg-red-50'
                                }`}>
                          {place.category}
                        </span>
                              </div>

                              <p className="mt-1 text-sm font-medium text-slate-500 truncate">
                                {place.time || '일정 확인 필요'}
                              </p>

                              <p className="mt-0.5 flex items-center gap-1 text-xs text-slate-400 font-medium whitespace-nowrap">
                                <span className="text-amber-400 text-sm">★</span>
                                <span className="text-slate-600 font-bold">{place.rating}</span>
                                <span>·</span>
                                <span className="truncate">리뷰 {place.reviews || '0'}</span>
                              </p>
                            </div>

                            <div className="flex items-center gap-0.5 shrink-0">
                              <button type="button" className="p-1 text-slate-300 hover:text-slate-400 cursor-grab">
                                <svg className="size-5" fill="currentColor" viewBox="0 0 20 20">
                                  <path d="M7 6a1 1 0 100-2 1 1 0 000 2zM7 11a1 1 0 100-2 1 1 0 000 2zM7 16a1 1 0 100-2 1 1 0 000 2zM13 6a1 1 0 100-2 1 1 0 000 2zM13 11a1 1 0 100-2 1 1 0 000 2zM13 16a1 1 0 100-2 1 1 0 000 2z" />
                                </svg>
                              </button>
                              <button type="button" onClick={() => handleDeletePlace(place.id)} className="rounded-full p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 active:bg-slate-200 transition-colors">
                                <svg className="size-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                                </svg>
                              </button>
                            </div>
                          </article>
                      ))
                  ) : (
                      <div className="flex flex-col items-center justify-center py-12 text-center border-2 border-dashed border-slate-100 rounded-2xl">
                        <span className="text-3xl mb-2">📍</span>
                        <p className="text-sm font-semibold text-slate-700">이날은 아직 루트가 없습니다</p>
                        <p className="text-xs text-slate-400 mt-1">장소 검색 탭에서 갈 곳들을 추가해보세요!</p>
                      </div>
                  )}
                </div>
              </div>
          )}
        </div>
      </aside>
  );
}