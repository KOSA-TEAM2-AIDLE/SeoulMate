import { memo, useState } from 'react';
import {
    getPlaceDisplayCategory,
    getPlaceDisplaySubCategory,
    getPlaceDisplayRating,
    getPlaceDisplayImage,
} from '../../services/map/placeDisplayAdapter';

const RouteItem = memo(({ place, index, isAccommodation, onDelete, onCycleCandidate, t }) => {
    const category = getPlaceDisplayCategory(place);
    const subCategory = getPlaceDisplaySubCategory(place);
    const rating = getPlaceDisplayRating(place);
    const image = getPlaceDisplayImage(place);
    const hasLink = !!place.link;
    const linkLabel = place.link?.toLowerCase().includes('tripadvisor.')
        ? t.travelerReviews
        : place.link?.toLowerCase().includes('booking.com')
            ? t.bookingLink
            : t.moreInfo;
    const canCycleCandidate = place.alternatives?.length > 0;

    const categoryStyles = {
        '카페': 'text-orange-500 bg-orange-50',
        '맛집': 'text-green-500 bg-green-50',
        '숙소': 'text-purple-500 bg-purple-50',
        '보관소': 'text-cyan-500 bg-cyan-50',
        default: 'text-red-500 bg-red-50'
    };

    const [imgError, setImgError] = useState(false);

    return (
        <article className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:border-slate-300 transition-all duration-200 relative">
            <div className="flex items-start gap-4">
                {/* 순서 마커 */}
                {isAccommodation ? (
                    <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-purple-100 text-purple-600 shadow-sm" title={t.accommodation || '숙소'}>
                        <svg className="size-4" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M19 7h-8v6h8V7zM5 7H3v10h2v-2h14v2h2V11a4 4 0 0 0-4-4H5zM5 9h8v4H5V9z"/>
                        </svg>
                    </div>
                ) : (
                    <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold text-white shadow-sm">
                        {index + 1}
                    </div>
                )}

                {/* 썸네일 이미지 */}
                <div className="flex size-16 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-slate-100 bg-slate-50">
                    {image && !imgError ? (
                        <img src={image} alt={place.name} className="h-full w-full object-cover" onError={() => setImgError(true)} />
                    ) : (
                        <span className="text-xs font-semibold text-slate-400">{t.noImage}</span>
                    )}
                </div>

                {/* 세부 텍스트 정보 */}
                <div className="flex-1 min-w-0 pr-8 space-y-1">
                    <div className="flex items-center gap-2">
                        <h3 className="font-bold text-slate-800 text-lg leading-snug truncate">
                            {place.name}
                        </h3>
                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded whitespace-nowrap shrink-0 ${categoryStyles[category] || categoryStyles.default}`}>
              {subCategory}
            </span>
                    </div>

                    <p className="text-sm text-slate-400 break-keep">{place.address}</p>

                    <div className="mt-1 min-h-[24px]">
                        <p className="text-sm text-amber-500 font-semibold flex items-center gap-1">
                            ★ {rating}
                        </p>
                    </div>

                    {(canCycleCandidate || hasLink) && (
                        <div className="mt-2 flex items-center gap-2">
                        {canCycleCandidate && (
                            <button
                                type="button"
                                onClick={() => onCycleCandidate(place)}
                                className="inline-flex flex-1 items-center justify-center whitespace-nowrap rounded bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-600 hover:bg-blue-100 border border-blue-100 transition-colors"
                            >
                                {t.changeCandidate}
                            </button>
                        )}
                        {hasLink && (
                            <a
                                href={place.link}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                aria-label={linkLabel}
                                title={linkLabel}
                                className="inline-flex flex-1 items-center justify-center gap-1 whitespace-nowrap rounded bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-200 border border-slate-200 transition-colors"
                            >
                                🔗 {linkLabel}
                            </a>
                        )}
                        </div>
                    )}
                </div>
            </div>

            {/* AI 추천 상세 블록 */}
            {place.selectionReason && (
                <div className="rounded-xl bg-slate-50 p-3.5 border border-slate-100 relative mt-1 mx-1">
                    <div
                        className="absolute top-0 left-[116px] -translate-y-[11px] w-4 h-3 bg-slate-50 border-t border-l border-slate-100"
                        style={{ clipPath: 'polygon(50% 0%, 0% 100%, 100% 100%)' }}
                    />
                    <p className="text-[13px] text-slate-600 leading-relaxed font-normal whitespace-pre-wrap break-keep relative z-10">
                        💡 {place.selectionReason}
                    </p>
                </div>
            )}

            {/* 삭제 버튼 */}
            <div className="absolute top-4 right-4 z-10">
                <button
                    type="button"
                    onClick={() => onDelete(place)}
                    className="rounded-full p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 active:bg-slate-200 transition-colors"
                    title={t.deleteRoute}
                >
                    <svg className="size-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </div>
        </article>
    );
});

RouteItem.displayName = 'RouteItem';
export default RouteItem;
