import assert from 'node:assert/strict';
import test from 'node:test';

import { getPlaceDisplayCategory } from './placeDisplayAdapter.js';

test('normalizes attraction API categories to the 명소 filter category', () => {
  assert.equal(getPlaceDisplayCategory({ category: '관광지' }), '명소');
  assert.equal(getPlaceDisplayCategory({ category: 'Attraction' }), '명소');
});
