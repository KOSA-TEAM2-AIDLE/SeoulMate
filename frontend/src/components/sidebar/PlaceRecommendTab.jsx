const PLACE_FILTERS = ['전체', '명소', '맛집', '카페', '숙소', '보관소'];

export default function PlaceRecommendTab({
                                           activeFilter,
                                           setActiveFilter,
                                           filteredPlaces,
                                           showToast
                                       }) {
    return (
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
                                activeFilter === filter
                                    ? 'border-blue-600 bg-blue-600 text-white'
                                    : 'border-slate-200 text-slate-600 bg-white hover:bg-slate-50'
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
                        <article
                            key={place.id}
                            onClick={() => showToast(`${place.name}이 선택되었습니다.`)}
                            className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:border-slate-300 transition-all cursor-pointer group"
                        >
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
                                    <p className="mt-1 text-sm text-slate-400 truncate">{place.address}</p>
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
    );
}