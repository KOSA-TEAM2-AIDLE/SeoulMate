import { create } from 'zustand';

const useLocationStore = create((set) => ({
  coordinates: null,
  isGeolocationSupported:
    typeof navigator !== 'undefined' && 'geolocation' in navigator,

  setCoordinates: (coordinates) => set({ coordinates }),
}));

export default useLocationStore;
