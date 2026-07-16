import { memo } from 'react';
import {
    getPlaceDisplayCategory,
    getPlaceDisplaySubCategory,
    getPlaceDisplayRating,
    getPlaceDisplayImage,
} from '../../services/map/placeDisplayAdapter';

const RouteItem = memo(({ place, index, onDelete, t }) => {
    const category = getPlaceDisplayCategory(place);
    const subCategory = getPlaceDisplaySubCategory(place);
    const rating = getPlaceDisplayRating(place);
    const image = getPlaceDisplayImage(place);
    const hasLink = !!place.link;

    const categoryStyles = {
        '카페': 'text-orange-500 bg-orange-50',
        '맛집': 'text-green-500 bg-green-50',
        '숙소': 'text-purple-500 bg-purple-50',
        '보관소': 'text-cyan-500 bg-cyan-50',
        default: 'text-red-500 bg-red-50'
    };

    return (
        <article className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:border-slate-300 transition-all duration-200 relative">
            <div className="flex items-start gap-4">
                {/* 순서 마커 */}
                <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold text-white shadow-sm">
                    {index + 1}
                </div>

                {/* 썸네일 이미지 */}
                <div className="flex size-16 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-slate-100 bg-slate-50">
                    {image ? (
                        <img src={image} alt={place.name} className="h-full w-full object-cover" />
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

                    <div className="flex items-center justify-between mt-1 min-h-[24px]">
                        <p className="text-sm text-amber-500 font-semibold flex items-center gap-1">
                            ★ {rating}
                        </p>

                        {hasLink && (
                            <a
                                href={place.link}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600 hover:bg-slate-200 border border-slate-200 transition-colors"
                            >
                                🔗 {t.moreInfo}
                            </a>
                        )}
                    </div>
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