import usePlaceRecommend from '../../hooks/sidebar/usePlaceRecommend';
import PlaceItem from './PlaceItem';

const PLACE_FILTERS = ['전체', '명소', '맛집', '카페', '숙소', '보관소'];

export default function PlaceRecommendTab({ activeFilter, setActiveFilter, filteredPlaces, showToast }) {
    const { t, filterTranslations, handlePlaceClick, lang } = usePlaceRecommend(showToast);

    return (
        <div className="flex-1 flex flex-col min-h-0">
            {/* 필터 탭 상단 헤더 */}
            <div className="pt-5 pb-3 space-y-4 shrink-0 border-b border-slate-50">
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
                            {filterTranslations[filter]}
                        </button>
                    ))}
                </div>

                <div className="flex items-center justify-between pt-1 px-5">
                    <h2 className="text-base font-bold text-slate-800">
                        {t.searchResult}
                    </h2>
                    <span className="text-sm text-slate-500">
                        {t.foundCount(filteredPlaces.length)}
                    </span>
                </div>
            </div>

            {/* 리스트 목록 영역 */}
            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3 min-h-0 bg-slate-50/40">
                {filteredPlaces.length > 0 ? (
                    filteredPlaces.map((place) => (
                        <PlaceItem
                            key={place.id}
                            place={place}
                            onClick={handlePlaceClick}
                            t={t}
                            lang={lang}
                        />
                    ))
                ) : (
                    <div className="text-center py-12 border-2 border-dashed border-slate-200 rounded-2xl text-slate-400 text-sm bg-white">
                        {t.noResult}
                    </div>
                )}
            </div>
        </div>
    );
}
