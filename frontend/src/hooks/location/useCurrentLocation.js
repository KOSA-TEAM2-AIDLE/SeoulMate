import { useEffect } from 'react';
import useLocationStore from '../../stores/useLocationStore';

export function useCurrentLocation() {
  const isGeolocationSupported = useLocationStore(
    (state) => state.isGeolocationSupported,
  );
  const setCoordinates = useLocationStore((state) => state.setCoordinates);

  useEffect(() => {
    if (!isGeolocationSupported) {
      return;
    }

    navigator.geolocation.getCurrentPosition((position) => {
      setCoordinates({
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
      });
    });
  }, [isGeolocationSupported, setCoordinates]);
}
