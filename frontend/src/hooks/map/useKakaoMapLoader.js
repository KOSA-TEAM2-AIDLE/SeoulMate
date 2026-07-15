import { useEffect, useState } from 'react';
import { loadKakaoMapSdk } from '../../services/map/kakaoMapLoader';

export function useKakaoMapLoader() {
  const [kakao, setKakao] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;

    async function loadSdk() {
      try {
        setIsLoading(true);
        setError(null);

        const kakaoMap = await loadKakaoMapSdk();

        if (isMounted) {
          setKakao(kakaoMap);
        }
      } catch (sdkError) {
        if (isMounted) {
          setError(sdkError);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadSdk();

    return () => {
      isMounted = false;
    };
  }, []);

  return {
    kakao,
    isLoading,
    isLoaded: Boolean(kakao),
    error,
  };
}