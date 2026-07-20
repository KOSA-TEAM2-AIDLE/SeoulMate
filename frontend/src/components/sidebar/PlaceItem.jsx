import { memo, useState } from 'react';
import { getPlaceDisplaySubCategory, getPlaceDisplayRating, getPlaceDisplayImage } from '../../services/map/placeDisplayAdapter';
import { getLocalizedPlaceSubCategory } from '../../services/display/localizedPlaceDisplay';

const PlaceItem = memo(({ place, onClick, t, lang }) => {
    const subCategory = getLocalizedPlaceSubCategory(
        { ...place, subCategory: place.subCategory || getPlaceDisplaySubCategory(place) },
        lang,
    );
    const rating = getPlaceDisplayRating(place);
    const image = getPlaceDisplayImage(place);
    const hasLink = !!place.link;
    const linkLabel = place.link?.toLowerCase().includes('tripadvisor.')
        ? t.travelerReviews
        : place.category === '숙소' ? t.reservation : t.moreInfo;

    console.log("PlaceItem Render:", place.name, place);

    const categoryStyles = {
        '카페': 'text-orange-500 bg-orange-50',
        '맛집': 'text-green-500 bg-green-50',
        '숙소': 'text-purple-500 bg-purple-50',
        '보관소': 'text-cyan-500 bg-cyan-50',
        default: 'text-red-500 bg-red-50'
    };

    const [imgError, setImgError] = useState(false);

    return (
        <article
            onClick={() => onClick(place)}
            className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:border-slate-300 transition-all cursor-pointer group relative"
        >
            <div className="flex gap-3">
                {/* 이미지 영역 */}
                <div className="flex size-16 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-slate-100 bg-slate-50">
                    {image && !imgError ? (
                        <img
                            src={image}
                            alt={place.name}
                            className="h-full w-full object-cover group-hover:scale-105 transition-transform duration-200"
                            onError={() => setImgError(true)}
                        />
                    ) : (
                        <span className="text-xs font-semibold text-slate-400">
                            {t.noImage}
                        </span>
                    )}
                </div>

                {/* 정보 영역 */}
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        <h3 className="font-bold text-slate-800 truncate text-base flex-1">
                            {place.name}
                        </h3>
                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0 whitespace-nowrap ${categoryStyles[place.category] || categoryStyles.default}`}>
                            {subCategory}
                        </span>
                    </div>

                    <p className="mt-1 text-sm text-slate-400 truncate">
                        {place.address}
                    </p>

                    {/* 하단 평점 및 외부 링크 */}
                    <div className="flex items-center justify-between mt-1.5 min-h-[24px]">
                        <p className="text-sm text-amber-500 font-semibold">
                            ★ {rating}
                        </p>

                        {hasLink && (
                            <a
                                href={place.link}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()} // 이벤트 전파 중단
                                className="inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600 hover:bg-slate-200 border border-slate-200 transition-colors"
                            >
                                🔗 {linkLabel}
                            </a>
                        )}
                    </div>
                </div>
            </div>

            {/* AI 추천 사유 */}
            {place.selectionReason && (
                <div className="mt-3.5 rounded-lg bg-slate-50 p-3 border border-slate-100 group-hover:bg-slate-100/50 transition-colors">
                    <div className="flex gap-1.5 items-center text-[11px] font-bold text-blue-600 mb-1">
                        💡 {t.aiReason}
                    </div>
                    <p className="text-xs leading-relaxed text-slate-600">
                        {place.selectionReason}
                    </p>
                </div>
            )}
        </article>
    );
});

PlaceItem.displayName = 'PlaceItem';
export default PlaceItem;
