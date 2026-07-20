import { useEffect, useState } from 'react';

import { loadNaverMapSdk } from '../../services/map/naverMapLoader';

export function useNaverMapLoader(language) {
  const [naver, setNaver] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);
    setError(null);
    setNaver(null);

    loadNaverMapSdk(language)
      .then((sdk) => {
        if (isMounted) setNaver(sdk);
      })
      .catch((sdkError) => {
        if (isMounted) setError(sdkError);
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [language]);

  return { naver, isLoading, isLoaded: Boolean(naver), error };
}
