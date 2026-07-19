import assert from 'node:assert/strict';
import test from 'node:test';

import { getTransitStepLabel, getTransitStepPresentation } from './transitStepService.js';

test('uses ODsay bus number in a transit step label', () => {
  assert.equal(getTransitStepLabel({ trafficType: 2, lane: [{ busNo: '470' }] }, 'Transit'), '470');
});

test('uses the localized walking fallback for walking steps', () => {
  assert.equal(getTransitStepLabel({ trafficType: 3 }, '도보'), '도보');
});

test('keeps individual walking and bus stages without a duplicated total walking stage', () => {
  const stages = getTransitStepPresentation(
    [
      { trafficType: 3, sectionTime: 4 },
      {
        trafficType: 2,
        sectionTime: 8,
        stationCount: 5,
        startName: '서울시청',
        endName: '종로3가',
        lane: [{ busNo: '501' }],
      },
      { trafficType: 3, sectionTime: 1 },
    ],
    { walk: 'Walk', transit: 'Transit', station: 'stops' },
  );

  assert.deepEqual(stages, [
    { label: 'Walk', minutes: 4, detail: null },
    { label: '501', minutes: 8, detail: '서울시청 → 종로3가 · 5 stops' },
    { label: 'Walk', minutes: 1, detail: null },
  ]);
});
