import useTravelStore from '../../stores/useTravelStore';
import { useLangStore } from '../../stores/useLangStore';

const FILTER_TRANSLATIONS = {
    ko: { '전체': '전체', '명소': '명소', '맛집': '맛집', '카페': '카페', '숙소': '숙소', '보관소': '보관소' },
    en: { '전체': 'All', '명소': 'Attractions', '맛집': 'Restaurants', '카페': 'Cafes', '숙소': 'Hotels', 'Luggage': 'Luggage' }
};

const UI_TEXT = {
    ko: {
        searchResult: '검색 결과',
        foundCount: (count) => `${count}개 발견`,
        noImage: '이미지 없음',
        noResult: '해당 카테고리의 결과가 존재하지 않습니다.',
        toastAdded: (day, name) => `${day}일차 루트에 '${name}'이(가) 추가되었습니다.`,
        toastDuplicate: (name) => `'${name}'은(는) 이미 해당 일차 루트에 존재합니다.`,
        aiReason: '추천 이유',
        moreInfo: '바로가기'
    },
    en: {
        searchResult: 'Search Results',
        foundCount: (count) => `${count} found`,
        noImage: 'No Image',
        noResult: 'No results found for this category.',
        toastAdded: (day, name) => `'${name}' has been added to Day ${day} path.`,
        toastDuplicate: (name) => `'${name}' is already in this day's path.`,
        aiReason: 'Why we recommend',
        moreInfo: 'Link'
    }
};

export default function usePlaceRecommend(showToast) {
    const selectedDay = useTravelStore((state) => state.selectedDay);
    const addPathItem = useTravelStore((state) => state.addPathItem);
    const lang = useLangStore((state) => state.lang);

    const t = UI_TEXT[lang] || UI_TEXT.ko;
    const filterTranslations = FILTER_TRANSLATIONS[lang] || FILTER_TRANSLATIONS.ko;

    const handlePlaceClick = (place) => {
        const isAdded = addPathItem(place);
        if (isAdded) {
            showToast(t.toastAdded(selectedDay, place.name));
        } else {
            showToast(t.toastDuplicate(place.name));
        }
    };

    return {
        t,
        filterTranslations,
        handlePlaceClick
    };
}