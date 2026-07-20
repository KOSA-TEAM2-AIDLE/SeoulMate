import { getRouteSegmentNavigationItems } from '../../services/map/routeSegmentNavigation';

const COPY = {
  ko: '이동 구간 선택',
  en: 'Select route segment',
};

export default function RouteSegmentNavigator({ places, activeIndex, language, onSelect }) {
  const items = getRouteSegmentNavigationItems(places);
  if (!items.length) return null;

  return <nav aria-label={COPY[language] ?? COPY.en} className="absolute z-10 top-4 left-1/2 flex max-w-[calc(100%-32px)] -translate-x-1/2 gap-1 overflow-x-auto rounded-xl border border-slate-200 bg-white/95 p-1 shadow-md backdrop-blur"><span className="sr-only">{COPY[language] ?? COPY.en}</span>{items.map((item) => <button key={item.index} type="button" onClick={() => onSelect(item.index)} aria-pressed={activeIndex === item.index} title={item.description} className={`shrink-0 rounded-lg px-3 py-1.5 text-xs font-bold transition ${activeIndex === item.index ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>{item.label}</button>)}</nav>;
}
