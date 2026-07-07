import { useState } from 'react';
import useTravelStore from '../../stores/useTravelStore';

export default function TravelRouteTab({ showToast }) {
    const [days] = useState([1, 2, 3]);

    const [viewDay, setViewDay] = useState(1);

    const travelPath = useTravelStore((state) => state.travelPath);
    const removePathItem = useTravelStore((state) => state.removePathItem);

    const currentRoute = travelPath[viewDay] || [];

    return (
        <div className="flex-1 flex flex-col min-h-0 p-5 space-y-6">
            {/* 상단 액션 바 */}
            <div className="flex items-center justify-between shrink-0">
                <h2 className="text-2xl font-bold text-slate-900 tracking-tight">내 여행 루트</h2>
                <div className="flex gap-2">
                    <button type="button" onClick={() => showToast('여행 루트가 정상적으로 저장되었습니다.')} className="flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-3.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-all shadow-sm">
                        저장
                    </button>
                    <button type="button" onClick={() => showToast('공유 링크가 클립보드에 복사되었습니다.')} className="flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-3.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-all shadow-sm">
                        공유
                    </button>
                </div>
            </div>

            {/* Day 탭 목록 */}
            <div className="flex flex-wrap items-center gap-2 shrink-0">
                {days.map((d) => (
                    <button
                        key={d}
                        type="button"
                        onClick={() => setViewDay(d)}
                        className={`rounded-full px-5 py-2.5 text-sm font-semibold transition-all shadow-sm ${
                            viewDay === d
                                ? 'bg-blue-600 text-white border border-blue-600'
                                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
                        }`}
                    >
                        Day {d}
                    </button>
                ))}
            </div>

            {/* 여행 루트 카드 리스트 */}
            <div className="flex-1 overflow-y-auto space-y-4 min-h-0 pr-1">
                {currentRoute.length > 0 ? (
                    currentRoute.map((place, index) => (
                        <article key={place.id} className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm hover:shadow-md transition-all duration-200">
                            <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold text-white shadow-sm">
                                {index + 1}
                            </div>

                            <div className="size-16 shrink-0 overflow-hidden rounded-xl border border-slate-100 bg-slate-50 shadow-inner">
                                <img src={place.image} alt={place.name} className="h-full w-full object-cover" />
                            </div>

                            <div className="flex-1 min-w-0 flex flex-col justify-center">
                                <div className="flex items-center justify-between gap-2">
                                    <h3 className="font-bold text-slate-900 truncate tracking-tight text-base flex-1">
                                        {place.name}
                                    </h3>
                                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded whitespace-nowrap shrink-0 ${
                                        place.category === '카페' ? 'text-orange-500 bg-orange-50' :
                                            place.category === '맛집' ? 'text-green-500 bg-green-50' :
                                                place.category === '숙소' ? 'text-purple-500 bg-purple-50' :
                                                    place.category === '보관소' ? 'text-cyan-500 bg-cyan-50' : 'text-red-500 bg-red-50'
                                    }`}>
                                        {place.category}
                                    </span>
                                </div>
                                <p className="mt-1 text-sm font-medium text-slate-500 truncate">
                                    {place.time || '일정 확인 필요'}
                                </p>
                                <p className="mt-0.5 flex items-center gap-1 text-xs text-slate-400 font-medium whitespace-nowrap">
                                    <span className="text-amber-400 text-sm">★</span>
                                    <span className="text-slate-600 font-bold">{place.rating}</span>
                                    <span>·</span>
                                    <span className="truncate">리뷰 {place.reviews || '0'}</span>
                                </p>
                            </div>

                            <div className="flex items-center gap-0.5 shrink-0">
                                <button type="button" className="p-1 text-slate-300 hover:text-slate-400 cursor-grab" title="순서 이동">
                                    <svg className="size-5" fill="currentColor" viewBox="0 0 20 20">
                                        <path d="M7 6a1 1 0 100-2 1 1 0 000 2zM7 11a1 1 0 100-2 1 1 0 000 2zM7 16a1 1 0 100-2 1 1 0 000 2zM13 6a1 1 0 100-2 1 1 0 000 2zM13 11a1 1 0 100-2 1 1 0 000 2zM13 16a1 1 0 100-2 1 1 0 000 2z" />
                                    </svg>
                                </button>
                                <button
                                    type="button"
                                    onClick={() => {
                                        const targetDay = Number(viewDay);
                                        removePathItem(targetDay, place.id);

                                        showToast(`${place.name}이 루트에서 삭제되었습니다.`);
                                    }}
                                    className="rounded-full p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 active:bg-slate-200 transition-colors"
                                    title="루트 삭제"
                                >
                                    <svg className="size-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                </button>
                            </div>
                        </article>
                    ))
                ) : (
                    <div className="flex flex-col items-center justify-center py-12 text-center border-2 border-dashed border-slate-100 rounded-2xl">
                        <span className="text-3xl mb-2">📍</span>
                        <p className="text-sm font-semibold text-slate-700">{viewDay}일차는 아직 루트가 없습니다</p>
                        <p className="text-xs text-slate-400 mt-1">장소 검색 탭에서 갈 곳들을 추가해보세요!</p>
                    </div>
                )}
            </div>
        </div>
    );
}