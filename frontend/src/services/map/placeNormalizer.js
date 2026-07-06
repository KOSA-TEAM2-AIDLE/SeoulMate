/* Prefix : 동일한 ID 값으로 인해 중복 발생 문제를 피함 */
const PLACE_TYPES = {
  CAFE: 'cafe',
  RESTAURANT: 'restaurant',
  ACCOMMODATION: 'accommodation',
  EVENT: 'event',
  STORAGE_LOCKER: 'storage-locker',
};

function hasValidCoordinates(place) {
  return Number.isFinite(place?.lat) && Number.isFinite(place?.lng);
}

function createMapPlace({
    type,
    sourceId,
    name,
    category,
    address,
    lat,
    lng,
    image = '',
    description = '',
    meta = {},
    raw
}) {
    return {
        id : `${type}:${sourceId}`,
        sourceId,
        type,
        name,
        category,
        address,
        lat,
        lng,
        image,
        description,
        meta,
        raw,
      };
}


export function normalizeCafe(cafe) {
  return createMapPlace({
    type: PLACE_TYPES.CAFE,
    sourceId: cafe.id,
    name: cafe.name,
    category: cafe.category,
    address: cafe.address,
    lat: cafe.lat,
    lng: cafe.lng,
    image: cafe.image,
    description: cafe.description,
    meta: {
      phone: cafe.phone,
      hours: cafe.hours,
      link: cafe.link,
      postalCode: cafe.postal_code,
    },
    raw: cafe,
  });
}

export function normalizeRestaurant(restaurant) {
  return createMapPlace({
    type: PLACE_TYPES.RESTAURANT,
    sourceId: restaurant.id,
    name: restaurant.name,
    category: restaurant.category,
    address: restaurant.address,
    lat: restaurant.lat,
    lng: restaurant.lng,
    image: restaurant.image,
    description: restaurant.description,
    meta: {
      phone: restaurant.phone,
      hours: restaurant.hours,
      link: restaurant.link,
      postalCode: restaurant.postal_code,
    },
    raw: restaurant,
  });
}

export function normalizeAccommodation(accommodation) {
  return createMapPlace({
    type: PLACE_TYPES.ACCOMMODATION,
    sourceId: accommodation.id,
    name: accommodation.name,
    category: accommodation.style,
    address: accommodation.road_address,
    lat: accommodation.lat,
    lng: accommodation.lng,
    image: accommodation.image,
    description: accommodation.languages,
    meta: {
      rating: accommodation.rating,
      reviewCount: accommodation.review_count,
      languages: accommodation.languages,
      link: accommodation.link,
    },
    raw: accommodation,
  });
}

export function normalizeEvent(event) {
  return createMapPlace({
    type: PLACE_TYPES.EVENT,
    sourceId: event.id,
    name: event.facility_name,
    category: event.facility_tag,
    address: event.road_address,
    lat: event.lat,
    lng: event.lng,
    image: event.image_url,
    description: event.facility_summary,
    meta: {
      placeName: event.place_name,
      startDate: event.start_date,
      endDate: event.end_date,
      hours: event.hours,
      hasFee: event.has_fee,
      fee: event.fee,
      homepageUrl: event.homepage_url,
      subwayInfo: event.subway_info,
    },
    raw: event,
  });
}

export function normalizeStorageLocker(locker) {
  return createMapPlace({
    type: PLACE_TYPES.STORAGE_LOCKER,
    sourceId: locker.id,
    name: locker.main_location,
    category: '물품보관함',
    address: locker.road_address,
    lat: locker.lat,
    lng: locker.lng,
    image: '',
    description: locker.description,
    meta: {
      detailLocation: locker.detail_location,
      lockerCount: locker.locker_count,
      hours: locker.hours,
      fee: locker.fee,
      paymentMethod: locker.payment_method,
      overtimeUnit: locker.overtime_unit,
      jibunAddress: locker.jibun_address,
    },
    raw: locker,
  });
}

function filterPlaceWithCoordinates(places){
    return places.filter(hasValidCoordinates);
}

export function normalizeMapPlaces({
  cafes = [],
  restaurants = [],
  accommodations = [],
  events = [],
  storageLockers = [],
}) {
  const normalizedPlaces = [
    ...cafes.map(normalizeCafe),
    ...restaurants.map(normalizeRestaurant),
    ...accommodations.map(normalizeAccommodation),
    ...events.map(normalizeEvent),
    ...storageLockers.map(normalizeStorageLocker),
  ];

  return filterPlaceWithCoordinates(normalizedPlaces);
}

export { PLACE_TYPES };