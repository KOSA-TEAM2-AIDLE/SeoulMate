import assert from 'node:assert/strict';
import test from 'node:test';

import { createRoutePolyline } from './polylineService.js';

test('adds a wide transparent interaction target for each route', () => {
  const options = [];
  const naver = {
    maps: {
      LatLng: class LatLng { constructor(lat, lng) { this.lat = lat; this.lng = lng; } },
      Polyline: class Polyline {
        constructor(value) { options.push(value); }
        setOptions() {}
      },
      Event: { addListener() {} },
    },
  };

  createRoutePolyline({
    naver,
    map: {},
    places: [{ lat: 37.5, lng: 126.9 }, { lat: 37.6, lng: 127.0 }],
    segments: [{ route: { mode: 'walk' } }],
  });

  assert.equal(options.length, 2);
  assert.equal(options[1].strokeWeight, 18);
  assert.equal(options[1].strokeOpacity, 0);
  assert.equal(options[1].clickable, true);
});

test('hides a transit fallback line when detailed geometry is active', () => {
  const options = [];
  const naver = {
    maps: {
      LatLng: class LatLng { constructor(lat, lng) { this.lat = lat; this.lng = lng; } },
      Polyline: class Polyline { constructor(value) { options.push(value); } setOptions() {} },
      Event: { addListener() {} },
    },
  };

  createRoutePolyline({
    naver,
    map: {},
    places: [{ lat: 37.5, lng: 126.9 }, { lat: 37.6, lng: 127.0 }],
    segments: [{ route: { mode: 'transit' } }],
    hiddenSegmentIndex: 0,
  });

  assert.equal(options.length, 0);
});

test('emphasizes the explicitly selected route segment', () => {
  const options = [];
  const naver = {
    maps: {
      LatLng: class LatLng { constructor(lat, lng) { this.lat = lat; this.lng = lng; } },
      Polyline: class Polyline { constructor(value) { options.push(value); } setOptions() {} },
      Event: { addListener() {} },
    },
  };

  createRoutePolyline({
    naver,
    map: {},
    places: [{ lat: 37.5, lng: 126.9 }, { lat: 37.6, lng: 127.0 }],
    segments: [{ route: { mode: 'walk' } }],
    selectedSegmentIndex: 0,
  });

  assert.equal(options[0].strokeWeight, 6);
  assert.equal(options[0].strokeOpacity, 1);
});
