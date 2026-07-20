const CATEGORY_KEYS = {
  관광지: 'attraction',
  Attraction: 'attraction',
  맛집: 'restaurant',
  Restaurant: 'restaurant',
  카페: 'cafe',
  Cafe: 'cafe',
  숙소: 'accommodation',
  Accommodation: 'accommodation',
};

const CATEGORY_LABELS = {
  attraction: { ko: '관광지', en: 'Attraction' },
  restaurant: { ko: '맛집', en: 'Restaurant' },
  cafe: { ko: '카페', en: 'Cafe' },
  accommodation: { ko: '숙소', en: 'Accommodation' },
};

const SUBCATEGORY_LABELS = {
  궁궐: { ko: '궁궐', en: 'Palace' },
  Palace: { ko: '궁궐', en: 'Palace' },
};

const locale = (lang) => (lang === 'en' ? 'en' : 'ko');

export function getLocalizedPlaceCategory(place, lang) {
  const key = CATEGORY_KEYS[place.category];
  return key ? CATEGORY_LABELS[key][locale(lang)] : place.category;
}

export function getLocalizedPlaceSubCategory(place, lang) {
  const label = SUBCATEGORY_LABELS[place.subCategory];
  return label ? label[locale(lang)] : place.subCategory || place.category;
}
