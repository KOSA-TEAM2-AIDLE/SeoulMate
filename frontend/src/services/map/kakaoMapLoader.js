const KAKAO_MAP_SDK_ID = 'kakao-map-sdk';

let kakaoMapLoaderPromise = null;

export function loadKakaoMapSdk() {
  if (window.kakao?.maps) {
    return Promise.resolve(window.kakao);
  }

  if (kakaoMapLoaderPromise) {
    return kakaoMapLoaderPromise;
  }

  const appKey = import.meta.env.VITE_KAKAO_MAP_APP_KEY;

  if (!appKey) {
    return Promise.reject(new Error('VITE_KAKAO_MAP_APP_KEY가 설정되지 않았습니다.'));
  }

  kakaoMapLoaderPromise = new Promise((resolve, reject) => {
    const existingScript = document.getElementById(KAKAO_MAP_SDK_ID);

    if (existingScript) {
      existingScript.addEventListener('load', () => {
        window.kakao.maps.load(() => {
          resolve(window.kakao);
        });
      });

      existingScript.addEventListener('error', () => {
        reject(new Error('Kakao Map SDK 로딩에 실패했습니다.'));
      });

      return;
    }

    const script = document.createElement('script');
    script.id = KAKAO_MAP_SDK_ID;
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${appKey}&autoload=false&libraries=services,clusterer`;
    script.async = true;

    script.onload = () => {
      window.kakao.maps.load(() => {
        resolve(window.kakao);
      });
    };

    script.onerror = () => {
      kakaoMapLoaderPromise = null;
      reject(new Error('Kakao Map SDK 로딩에 실패했습니다.'));
    };

    document.head.appendChild(script);
  });

  return kakaoMapLoaderPromise;
}