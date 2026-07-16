import React from 'react';
import useTravelStore from '../../stores/useTravelStore';
import { useLangStore } from '../../stores/useLangStore';
import { getPlaceDisplaySubCategory, getPlaceDisplayRating, getPlaceDisplayImage } from '../../services/map/placeDisplayAdapter';

const FILTER_TRANSLATIONS = {
    ko: {
        '전체': '전체',
        '명소': '명소',
        '맛집': '맛집',
        '카페': '카페',
        '숙소': '숙소',
        '보관소': '보관소'
    },
    en: {
        '전체': 'All',
        '명소': 'Attractions',
        '맛집': 'Restaurants',
        '카페': 'Cafes',
        '숙소': 'Hotels',
        '보관소': 'Luggage'
    }
};

const UI_TEXT = {
    ko: {
        searchResult: '검색 결과',
        foundCount: (count) => `${count}개 발견`,
        noImage: '이미지 없음',
        noResult: '해당 카테고리의 결과가 존재하지 않습니다.',
        toastAdded: (day, name) => `${day}일차 루트에 '${name}'이(가) 추가되었습니다.`,
        toastDuplicate: (name) => `'${name}'은(는) 이미 해당 일차 루트에 존재합니다.`,
        aiReason: '추천 이유'
    },
    en: {
        searchResult: 'Search Results',
        foundCount: (count) => `${count} found`,
        noImage: 'No Image',
        noResult: 'No results found for this category.',
        toastAdded: (day, name) => `'${name}' has been added to Day ${day} path.`,
        toastDuplicate: (name) => `'${name}' is already in this day's path.`,
        aiReason: 'Why we recommend'
    }
};

const PLACE_FILTERS = ['전체', '명소', '맛집', '카페', '숙소', '보관소'];

export default function PlaceRecommendTab({ activeFilter, setActiveFilter, filteredPlaces, showToast }) {
    const selectedDay = useTravelStore((state) => state.selectedDay);
    const addPathItem = useTravelStore((state) => state.addPathItem);

    const lang = useLangStore((state) => state.lang);
    const t = UI_TEXT[lang];

    return (
        <div className="flex-1 flex flex-col min-h-0">
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
                            {FILTER_TRANSLATIONS[lang][filter]}
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

            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3 min-h-0 bg-slate-50/40">
                {filteredPlaces.length > 0 ? (
                    filteredPlaces.map((place) => {
                        const subCategory = getPlaceDisplaySubCategory(place);
                        const rating = getPlaceDisplayRating(place);
                        const image = getPlaceDisplayImage(place);

                        return (
                            <article
                                key={place.id}
                                onClick={() => {
                                    const isAdded = addPathItem(place);

                                    if (isAdded) {
                                        showToast(t.toastAdded(selectedDay, place.name));
                                    } else {
                                        showToast(t.toastDuplicate(place.name));
                                    }
                                }}
                                className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:border-slate-300 transition-all cursor-pointer group"
                            >
                                <div className="flex gap-3">
                                    <div className="flex size-16 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-slate-100 bg-slate-50">
                                        {image ? (
                                            <img
                                                src={image}
                                                alt={place.name}
                                                className="h-full w-full object-cover group-hover:scale-105 transition-transform duration-200"
                                            />
                                        ) : (
                                            <span className="text-xs font-semibold text-slate-400">
                                                {t.noImage}
                                            </span>
                                        )}
                                    </div>

                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2">
                                            <h3 className="font-bold text-slate-800 truncate text-base flex-1">
                                                {place.name}
                                            </h3>

                                            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0 whitespace-nowrap ${
                                                place.category === '카페' ? 'text-orange-500 bg-orange-50' :
                                                    place.category === '맛집' ? 'text-green-500 bg-green-50' :
                                                        place.category === '숙소' ? 'text-purple-500 bg-purple-50' :
                                                            place.category === '보관소' ? 'text-cyan-500 bg-cyan-50' : 'text-red-500 bg-red-50'
                                            }`}>
                                                {subCategory}
                                            </span>
                                        </div>

                                        <p className="mt-1 text-sm text-slate-400 truncate">
                                            {place.address}
                                        </p>

                                        <p className="mt-1.5 text-sm text-amber-500 font-semibold">
                                            ★ {rating}
                                        </p>
                                    </div>
                                </div>

                                {place.selectionReason && (
                                    <div className="mt-3.5 rounded-lg bg-slate-50 p-3 border border-slate-100 group-hover:bg-slate-100/50 transition-colors">
                                        <div className="flex gap-1.5 items-center text-[11px] font-bold text-blue-600 mb-1">
                                            💡 {t.aiReason}
                                        </div>
                                        <p className="text-xs leading-relaxed text-slate-600">
                                            {place.selectionReason}
                                        </p>
                                    </div>
                                )}
                            </article>
                        );
                    })
                ) : (
                    <div className="text-center py-12 border-2 border-dashed border-slate-200 rounded-2xl text-slate-400 text-sm bg-white">
                        {t.noResult}
                    </div>
                )}
            </div>
        </div>
    );
}