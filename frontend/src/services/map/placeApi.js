import api from '../../api/axios';
import { normalizeMapPlaces } from './placeNormalizer';

export async function getCafes(lang='ko') {
    const response = await api.get('/cafes', {
        params : { lang }
    })
    return response.data;
}

export async function getRestaurants(lang = 'ko') {
  const response = await api.get('/restaurants', {
    params: { lang },
  });

  return response.data;
}

export async function getAccommodations(lang = 'ko') {
  const response = await api.get('/accommodations', {
    params: { lang },
  });

  return response.data;
}

export async function getEvents(lang = 'ko') {
  const response = await api.get('/events', {
    params: {
      lang,
      limit: 20,
    },
  });

  return response.data;
}

export async function getStorageLockers(lang = 'ko') {
  const response = await api.get('/storage-lockers', {
    params: { lang },
  });

  return response.data;
}

export async function getMapPlaces(lang = "ko"){
    const [
        cafes,
        restaurants,
        accommodations,
        events,
        storageLockers,
    ] = await Promise.all([
        getCafes(lang),
        getRestaurants(lang),
        getAccommodations(lang),
        getEvents(lang),
        getStorageLockers(lang)
    ]);

    return normalizeMapPlaces({
          cafes,
          restaurants,
          accommodations,
          events,
          storageLockers,
        });
}