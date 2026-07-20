import assert from 'node:assert/strict';
import test from 'node:test';

import { getNaverMapSdkUrl } from './naverMapLoader.js';

test('builds an English NAVER Maps SDK URL from the client ID', () => {
  assert.equal(
    getNaverMapSdkUrl('client-id'),
    'https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=client-id&language=en',
  );
});

test('rejects an empty NAVER Maps client ID', () => {
  assert.throws(
    () => getNaverMapSdkUrl(''),
    /VITE_NAVER_MAP_CLIENT_ID/,
  );
});
