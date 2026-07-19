import { Fragment } from 'react';
import { useLangStore } from '../../stores/useLangStore';
import { getTransitStepPresentation } from '../../services/map/transitStepService';
import { getNaverMapDirectionsUrl } from '../../services/map/naverMapDirectionsLink';

const COPY = {
  ko: {
    empty: '지도에서 이동 구간을 선택하세요.',
    minute: '분',
    transfers: '환승',
    walk: '도보',
    walkEstimate: '도보 약',
    walkNotice: '직선거리 기준 예상 시간입니다.',
    routeUnavailable: '대중교통 경로를 불러오지 못했습니다.',
    dataSource: 'ODsay 대중교통 정보',
    transit: '대중교통',
    station: '정거장',
    openNaverMap: 'NAVER 지도에서 길찾기',
  },
  en: {
    empty: 'Select a route segment to view transit details.',
    minute: 'min',
    transfers: 'transfers',
    walk: 'Walk',
    walkEstimate: 'Estimated walk',
    walkNotice: 'Estimate based on straight-line distance.',
    routeUnavailable: 'Transit route is unavailable.',
    dataSource: 'ODsay transit data',
    transit: 'Transit',
    station: 'stops',
    openNaverMap: 'Open in NAVER Map',
  },
};

function DirectionsButton({ origin, destination, mode, copy }) {
  const directionsUrl = getNaverMapDirectionsUrl(origin, destination, window.location.origin, navigator.userAgent, mode);
  const isAppUrl = directionsUrl.startsWith('nmap:');
  return <a href={directionsUrl} target={isAppUrl ? undefined : '_blank'} rel={isAppUrl ? undefined : 'noopener noreferrer'} aria-label={copy.openNaverMap} title={copy.openNaverMap} className="inline-flex size-8 shrink-0 items-center justify-center rounded-full border border-green-600 text-green-700 hover:bg-green-50"><svg viewBox="0 0 24 24" aria-hidden="true" className="size-4 fill-current"><path d="M12 2 4.5 19.5 12 16l7.5 3.5L12 2Zm0 3.1 4.35 10.15L12 13.2l-4.35 2.05L12 5.1Z" /></svg></a>;
}

export default function TransitRouteCard({ segment }) {
  const language = useLangStore((state) => state.lang);
  const copy = COPY[language] ?? COPY.en;

  if (!segment) return <div className="absolute z-10 bottom-5 left-1/2 w-[min(520px,calc(100%-40px))] -translate-x-1/2 rounded-xl border border-slate-200 bg-white p-4 shadow-lg text-sm text-slate-500">{copy.empty}</div>;
  const { origin, destination, route } = segment;
  if (route.mode === 'walk') {
    return <div className="absolute z-10 bottom-5 left-1/2 w-[min(520px,calc(100%-40px))] -translate-x-1/2 rounded-xl border border-slate-200 bg-white p-4 shadow-lg"><div className="flex items-start gap-2"><DirectionsButton origin={origin} destination={destination} mode="walk" copy={copy} /><div><p className="font-bold text-slate-900">{origin.name} → {destination.name}</p><p className="mt-1 text-sm text-slate-600">{copy.walkEstimate} {route.duration_minutes} {copy.minute} · {route.distance_meters}m</p><p className="mt-2 text-xs text-slate-400">{copy.walkNotice}</p></div></div></div>;
  }
  if (route.mode === 'unavailable') {
    return <div className="absolute z-10 bottom-5 left-1/2 w-[min(520px,calc(100%-40px))] -translate-x-1/2 rounded-xl border border-slate-200 bg-white p-4 shadow-lg"><p className="font-bold text-slate-900">{origin.name} → {destination.name}</p><p className="mt-1 text-sm text-slate-600">{copy.routeUnavailable}</p><p className="mt-2 text-xs text-slate-400">{route.error}</p></div>;
  }
  const stages = getTransitStepPresentation(route.steps, copy);
  const transitDetails = stages.filter((stage) => stage.detail);
  return <div className="absolute z-10 bottom-5 left-1/2 w-[min(520px,calc(100%-40px))] -translate-x-1/2 rounded-xl border border-slate-200 bg-white p-4 shadow-lg"><p className="font-bold text-slate-900">{origin.name} → {destination.name}</p><p className="mt-1 text-sm text-slate-600">{route.duration_minutes ?? '-'} {copy.minute} · {route.transfers ?? 0} {copy.transfers} · ₩{route.fare ?? 0}</p><p className="mt-2 text-xs text-slate-400">{copy.dataSource}</p><div className="mt-3 flex items-start gap-2"><DirectionsButton origin={origin} destination={destination} mode="public" copy={copy} /><div className="min-w-0"><div className="flex flex-wrap items-center gap-1">{stages.map((stage, index) => <Fragment key={`stage-group-${index}`}><span className="rounded bg-blue-50 px-2 py-1 text-xs text-blue-700">{stage.label}{stage.minutes ? ` · ${stage.minutes}${copy.minute}` : ''}</span>{index < stages.length - 1 && <span className="text-xs font-bold text-slate-400">→</span>}</Fragment>)}</div>{transitDetails.length > 0 && <div className="mt-2 space-y-1 text-xs text-slate-500">{transitDetails.map((stage, index) => <p key={`${stage.label}-${index}`} className="truncate">{stage.label} · {stage.detail}</p>)}</div>}</div></div></div>;
}
