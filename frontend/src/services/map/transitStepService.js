export function getTransitStepLabel(step, fallbackLabel) {
  if (step.trafficType === 3) return fallbackLabel;
  const lane = step.lane?.[0];
  if (step.trafficType === 2) return lane?.busNo ?? lane?.name ?? fallbackLabel;
  return lane?.name ?? lane?.subwayName ?? lane?.subwayCode ?? fallbackLabel;
}

export function getTransitStepPresentation(steps, copy) {
  return (steps ?? []).map((step) => ({
    label: getTransitStepLabel(step, step.trafficType === 3 ? copy.walk : copy.transit),
    minutes: step.sectionTime ?? null,
    detail: step.trafficType === 3 || !step.startName || !step.endName
      ? null
      : [
        `${step.startName} → ${step.endName}`,
        Number.isFinite(step.stationCount) ? `${step.stationCount} ${copy.station}` : null,
      ].filter(Boolean).join(' · '),
  }));
}
