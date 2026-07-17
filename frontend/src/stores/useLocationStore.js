import { create } from 'zustand';

const useLocationStore = create((set) => ({
  coordinates: null,
  isGeolocationSupported:
    typeof navigator !== 'undefined' && 'geolocation' in navigator,
  status: 'idle',
  error: null,

  startLocationRequest: () => set({ status: 'loading', error: null }),

  setLocationSuccess: (coordinates) =>
    set({
      coordinates,
      status: 'success',
      error: null,
    }),

  setLocationError: (error) =>
    set({ status: 'error', error }),
}));

export default useLocationStore;
