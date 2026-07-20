import assert from 'node:assert/strict';
import test from 'node:test';

import {
  getLocalizedPlaceCategory,
  getLocalizedPlaceSubCategory,
} from './localizedPlaceDisplay.js';

test('localizes attraction labels without mutating the place', () => {
  const place = { category: '관광지', subCategory: '궁궐' };

  assert.equal(getLocalizedPlaceCategory(place, 'en'), 'Attraction');
  assert.equal(getLocalizedPlaceSubCategory(place, 'en'), 'Palace');
  assert.equal(place.category, '관광지');
});

test('returns Korean fixed labels after language changes', () => {
  const place = { category: 'Attraction', subCategory: 'Palace' };

  assert.equal(getLocalizedPlaceCategory(place, 'ko'), '관광지');
  assert.equal(getLocalizedPlaceSubCategory(place, 'ko'), '궁궐');
});
