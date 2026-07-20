import assert from 'node:assert/strict';
import test from 'node:test';

import { getRouteSegmentNavigationItems } from './routeSegmentNavigation.js';

test('creates numbered route selector items from adjacent places', () => {
  const items = getRouteSegmentNavigationItems([
    { name: '서울광장' },
    { name: '서울문화라운지' },
    { name: '청계천' },
  ]);

  assert.deepEqual(items, [
    { index: 0, label: '서울광장 → 서울문화라운지', description: '서울광장 → 서울문화라운지' },
    { index: 1, label: '서울문화라운지 → 청계천', description: '서울문화라운지 → 청계천' },
  ]);
});
