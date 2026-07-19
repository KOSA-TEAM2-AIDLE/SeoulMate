import assert from 'node:assert/strict';
import test from 'node:test';

import {
  createWalkSegment,
  isWalkablePair,
} from './transitSegmentService.js';

test('creates a walking estimate for nearby places', () => {
  const segment = createWalkSegment(
    { id: 'a', lat: 37.5268, lng: 126.9222 },
    { id: 'b', lat: 37.5252, lng: 126.9291 },
  );

  assert.equal(segment.route.mode, 'walk');
  assert.ok(segment.route.distance_meters > 0);
  assert.ok(segment.route.duration_minutes > 0);
  assert.equal(segment.route.walking_minutes, segment.route.duration_minutes);
});

test('classifies pairs below 700 metres as walking', () => {
  assert.equal(isWalkablePair(699), true);
  assert.equal(isWalkablePair(700), false);
});
