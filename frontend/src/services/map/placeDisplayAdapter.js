export function getPlaceDisplayCategory(place) {
  const typeLabelMap = {
    cafe: '카페',
    restaurant: '맛집',
    accommodation: '숙소',
    event: '명소',
    'storage-locker': '보관소',
  };

  const category = typeLabelMap[place.type] || place.category || '장소';
  if (category === '관광지' || category === 'Attraction') return '명소';
  return category;
}

export function getPlaceDisplaySubCategory(place) {
  return place.category || place.meta?.style || place.type || '기타';
}

export function getDistinctPlaceDisplaySubCategory(place) {
  const category = getPlaceDisplayCategory(place);
  const subCategory = getPlaceDisplaySubCategory(place);
  return category === subCategory ? '' : subCategory;
}

export function getPlaceDisplayRating(place) {
  return place.meta?.rating ?? place.rating ?? '-';
}

export function getPlaceDisplayReviews(place) {
  return place.meta?.reviewCount ?? place.reviews ?? '0';
}

export function getPlaceDisplayTime(place) {
  return place.routeTime || place.time || place.meta?.hours || '일정 확인 필요';
}

export function getPlaceDisplayImage(place) {
  return place.image || place.routeMeta?.image || '';
}

export function getPlaceDisplayLink(place) {
  const link = place.link || place.meta?.link || place.meta?.homepageUrl || place.raw?.link || place.raw?.homepage_url || '';

  try {
    const url = new URL(link);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
  } catch {
    return '';
  }
}
