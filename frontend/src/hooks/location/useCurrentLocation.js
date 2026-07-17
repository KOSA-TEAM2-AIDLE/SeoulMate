import { useCallback, useEffect, useRef } from 'react';
import useLocationStore from '../../stores/useLocationStore';

const LOCATION_ERROR_MESSAGES = {
  1: '위치 정보 접근 권한이 거부되었습니다.',
  2: '현재 위치를 확인할 수 없습니다.',
  3: '위치 정보 요청 시간이 초과되었습니다.',
};

export function useCurrentLocation(autoRequest = true) {
  const hasRequested = useRef(false);
  const isGeolocationSupported = useLocationStore(
    (state) => state.isGeolocationSupported,
  );
  const startLocationRequest = useLocationStore(
    (state) => state.startLocationRequest,
  );
  const setLocationSuccess = useLocationStore(
    (state) => state.setLocationSuccess,
  );
  const setLocationError = useLocationStore((state) => state.setLocationError);

  const requestCurrentLocation = useCallback(() => {
    if (!isGeolocationSupported) {
      setLocationError({
        code: 'UNSUPPORTED',
        message: '이 브라우저는 위치 정보 기능을 지원하지 않습니다.',
      });
      return;
    }

    startLocationRequest();
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocationSuccess({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        });
      },
      (error) => {
        setLocationError({
          code: error.code,
          message:
            LOCATION_ERROR_MESSAGES[error.code] ??
            '위치 정보를 가져오는 중 오류가 발생했습니다.',
        });
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 300000,
      },
    );
  }, [
    isGeolocationSupported,
    setLocationError,
    setLocationSuccess,
    startLocationRequest,
  ]);

  useEffect(() => {
    if (!autoRequest || hasRequested.current) {
      return;
    }

    hasRequested.current = true;
    requestCurrentLocation();
  }, [autoRequest, requestCurrentLocation]);

  return { requestCurrentLocation };
}
