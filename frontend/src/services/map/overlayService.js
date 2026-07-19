import { useLangStore } from '../../stores/useLangStore';
import {
  getPlaceDisplayCategory,
  getPlaceDisplayRating,
  getPlaceDisplayReviews,
  getPlaceDisplaySubCategory,
} from './placeDisplayAdapter';

const CATEGORY_STYLE_BY_LABEL = {
  카페: {
    badgeClass: 'bg-orange-50 text-orange-500',
  },
  맛집: {
    badgeClass: 'bg-green-50 text-green-500',
  },
  숙소: {
    badgeClass: 'bg-purple-50 text-purple-500',
  },
  보관소: {
    badgeClass: 'bg-cyan-50 text-cyan-500',
  },
  명소: {
    badgeClass: 'bg-red-50 text-red-500',
  },
};

function escapeHtml(value) {
  return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
}

function createOverlayContent(place, onClose) {
  const category = getPlaceDisplayCategory(place);
  const subCategory = getPlaceDisplaySubCategory(place);
  const rating = getPlaceDisplayRating(place);
  const reviews = getPlaceDisplayReviews(place);

  const lang = useLangStore.getState().lang;

  const categoryStyle = CATEGORY_STYLE_BY_LABEL[category] ?? {
    badgeClass: 'bg-slate-100 text-slate-500',
  };

  const content = document.createElement('div');
  content.className = 'relative w-[260px] -translate-y-2 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-lg';
  content.innerHTML = `
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <div class="mb-1.5 flex items-center gap-1.5">
          <span class="rounded-full px-2 py-0.5 text-[11px] font-bold ${categoryStyle.badgeClass}">
            ${escapeHtml(category)}
          </span>
          <span class="truncate text-[11px] font-semibold text-slate-400">
            ${escapeHtml(subCategory)}
          </span>
        </div>
        <h3 class="truncate text-sm font-bold text-slate-900">
          ${escapeHtml(place.name)}
        </h3>
      </div>

      <button
        type="button"
        data-overlay-close="true"
        class="flex size-6 shrink-0 items-center justify-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        aria-label="${lang === 'ko' ? '오버레이 닫기' : 'Close overlay'}"
      >
        ×
      </button>
    </div>

    <p class="mt-1.5 truncate text-xs font-medium text-slate-500">
      ${escapeHtml(place.address)}
    </p>

    <p class="mt-2 flex items-center gap-1 text-xs font-medium text-slate-400">
      <span class="text-sm text-amber-400">★</span>
      <span class="font-bold text-slate-700">${escapeHtml(rating)}</span>
      <span>·</span>
      <span>
        ${lang === 'ko' ? `리뷰 ${escapeHtml(reviews)}` : `${escapeHtml(reviews)} Reviews`}
      </span>
    </p>

    <div class="absolute left-1/2 top-full size-3 -translate-x-1/2 -translate-y-1/2 rotate-45 border-b border-r border-slate-200 bg-white"></div>
  `;

  content.querySelector('[data-overlay-close="true"]')?.addEventListener('click', (event) => {
    event.stopPropagation();
    onClose?.();
  });

  return content;
}

export function createPlaceOverlay({ naver, map, place, onClose }) {
  if (!naver || !map || !place) {
    return null;
  }

  const position = new naver.maps.LatLng(place.lat, place.lng);
  const content = createOverlayContent(place, onClose);

  const infoWindow = new naver.maps.InfoWindow({ content, borderWidth: 0, backgroundColor: 'transparent', disableAnchor: true, pixelOffset: new naver.maps.Point(0, -28) });
  infoWindow.open(map, position);
  return infoWindow;
}

export function clearPlaceOverlay(overlay) {
  overlay?.setMap(null);
}
