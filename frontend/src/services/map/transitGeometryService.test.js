import assert from 'node:assert/strict';
import test from 'node:test';

import {
  extractGeometryPaths,
  extractGeometryPlaces,
  extractTransitWalkPaths,
} from './transitGeometryService.js';

test('extracts longitude-latitude paths from ODsay lane sections', () => {
  const paths = extractGeometryPaths({
    lane: [{
      section: [{ graphPos: [{ x: 126.97, y: 37.57 }, { x: 126.98, y: 37.56 }] }],
    }],
  });

  assert.deepEqual(paths, [[[126.97, 37.57], [126.98, 37.56]]]);
});

test('converts every ODsay geometry point into a map fitting place', () => {
  const places = extractGeometryPlaces({
    lane: [{
      section: [{ graphPos: [{ x: 126.97, y: 37.57 }, { x: 127.03, y: 37.50 }] }],
    }],
  });

  assert.deepEqual(places, [{ lat: 37.57, lng: 126.97 }, { lat: 37.50, lng: 127.03 }]);
});

test('creates dashed walking connectors around a transit section', () => {
  const paths = extractTransitWalkPaths({
    origin: { lat: 37.57, lng: 126.97 },
    destination: { lat: 37.50, lng: 127.04 },
    route: {
      steps: [{
        trafficType: 2,
        startX: 126.98,
        startY: 37.56,
        endX: 127.03,
        endY: 37.51,
      }],
    },
  });

  assert.deepEqual(paths, [
    [{ lat: 37.57, lng: 126.97 }, { lat: 37.56, lng: 126.98 }],
    [{ lat: 37.51, lng: 127.03 }, { lat: 37.50, lng: 127.04 }],
  ]);
});
