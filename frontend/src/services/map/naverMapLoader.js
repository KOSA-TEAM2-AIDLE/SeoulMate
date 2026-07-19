const NAVER_MAP_SDK_ID = 'naver-map-sdk';

let naverMapLoaderPromise = null;
let naverMapLoaderLanguage = null;

export function getNaverMapSdkUrl(clientId, language = 'en') {
  if (!clientId) {
    throw new Error('VITE_NAVER_MAP_CLIENT_ID가 설정되지 않았습니다.');
  }

  const query = new URLSearchParams({
    ncpKeyId: clientId,
    language,
  });

  return `https://oapi.map.naver.com/openapi/v3/maps.js?${query}`;
}

export function loadNaverMapSdk(language = 'en') {
  const loadedScript = document.getElementById(NAVER_MAP_SDK_ID);
  if (window.naver?.maps && loadedScript?.dataset.language === language) {
    return Promise.resolve(window.naver);
  }

  if (naverMapLoaderPromise && naverMapLoaderLanguage === language) {
    return naverMapLoaderPromise;
  }

  const clientId = import.meta.env.VITE_NAVER_MAP_CLIENT_ID;
  const src = getNaverMapSdkUrl(clientId, language);

  naverMapLoaderPromise = new Promise((resolve, reject) => {
    let existingScript = document.getElementById(NAVER_MAP_SDK_ID);

    if (existingScript && existingScript.dataset.language !== language) {
      existingScript.remove();
      window.naver = undefined;
      naverMapLoaderPromise = null;
      naverMapLoaderLanguage = null;
      existingScript = null;
    }

    if (existingScript) {
      existingScript.addEventListener('load', () => resolve(window.naver));
      existingScript.addEventListener('error', () => reject(new Error('NAVER Map SDK 로딩에 실패했습니다.')));
      return;
    }

    const script = document.createElement('script');
    script.id = NAVER_MAP_SDK_ID;
    script.dataset.language = language;
    script.src = src;
    script.async = true;
    script.onload = () => {
      if (window.naver?.maps) {
        resolve(window.naver);
        return;
      }
      naverMapLoaderPromise = null;
      naverMapLoaderLanguage = null;
      reject(new Error('NAVER Map SDK가 로드됐지만 naver.maps 객체를 생성하지 못했습니다. Client ID와 Web Dynamic Map 활성화 상태를 확인하세요.'));
    };
    script.onerror = () => {
      naverMapLoaderPromise = null;
      naverMapLoaderLanguage = null;
      reject(new Error('NAVER Map SDK 로딩에 실패했습니다.'));
    };
    document.head.appendChild(script);
  });
  naverMapLoaderLanguage = language;

  return naverMapLoaderPromise;
}
