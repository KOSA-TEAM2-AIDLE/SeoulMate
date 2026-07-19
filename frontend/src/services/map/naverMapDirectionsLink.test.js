import assert from 'node:assert/strict';
import test from 'node:test';

import {
  createNaverRouteAppUrl,
  createNaverTransitAppUrl,
  getNaverMapDirectionsUrl,
} from './naverMapDirectionsLink.js';

test('creates a NAVER Maps public-transit app route with both places', () => {
  const url = new URL(createNaverTransitAppUrl(
    { name: '출발지', address: '서울 중구 세종대로 110', lat: 37.5665, lng: 126.978 },
    { name: '도착지', address: '서울 종로구 청계천로 85', lat: 37.57, lng: 126.99 },
    'https://seoulmate.example',
  ));

  assert.equal(url.protocol, 'nmap:');
  assert.equal(url.hostname, 'route');
  assert.equal(url.pathname, '/public');
  assert.equal(url.searchParams.get('slat'), '37.5665');
  assert.equal(url.searchParams.get('sname'), '출발지 · 서울 중구 세종대로 110');
  assert.equal(url.searchParams.get('dname'), '도착지 · 서울 종로구 청계천로 85');
});

test('uses the desktop NAVER Maps directions page outside mobile browsers', () => {
  const url = getNaverMapDirectionsUrl(
    { name: '출발지', address: '서울 중구 세종대로 110', lat: 37.5665, lng: 126.978 },
    { name: '도착지', address: '서울 종로구 청계천로 85', lat: 37.57, lng: 126.99 },
    'https://seoulmate.example',
    'Mozilla/5.0',
  );

  assert.match(url, /^https:\/\/map\.naver\.com\/p\/directions\/\d+\.\d+,\d+\.\d+,.+,,ADDRESS_POI\/\d+\.\d+,\d+\.\d+,.+,,ADDRESS_POI\/-\/transit\?/);
  assert.match(decodeURIComponent(url), /출발지 · 서울 중구 세종대로 110/);
  assert.match(decodeURIComponent(url), /도착지 · 서울 종로구 청계천로 85/);
});

test('creates a walking route URL and preserves its route mode on mobile', () => {
  const origin = { name: 'A', address: '서울 중구 A로 1', lat: 37.5665, lng: 126.978 };
  const destination = { name: 'B', address: '서울 중구 B로 2', lat: 37.57, lng: 126.99 };

  assert.equal(new URL(createNaverRouteAppUrl(origin, destination, 'https://seoulmate.example', 'walk')).pathname, '/walk');
  assert.equal(
    new URL(getNaverMapDirectionsUrl(origin, destination, 'https://seoulmate.example', 'Android', 'walk')).pathname,
    '/walk',
  );
});
