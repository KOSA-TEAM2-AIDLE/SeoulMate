import useTravelStore from '../../stores/useTravelStore';
import { useLangStore } from '../../stores/useLangStore';
import {
  getPlaceDisplayCategory,
  getPlaceDisplaySubCategory,
  getPlaceDisplayRating,
  getPlaceDisplayImage,
} from '../../services/map/placeDisplayAdapter';

const UI_TEXT = {
  ko: {
    title: '내 여행 루트',
    saveBtn: '저장',
    shareBtn: '공유',
    noImage: '이미지 없음',
    deleteRoute: '루트 삭제',
    toastSave: '여행 루트가 정상적으로 저장되었습니다.',
    toastShare: '공유 링크가 클립보드에 복사되었습니다.',
    toastDelete: (name) => `${name}이 루트에서 삭제되었습니다.`,
    noRouteTitle: (day) => `${day}일차는 아직 루트가 없습니다`,
    noRouteDesc: '장소 검색 탭에서 갈 곳들을 추가해보세요!'
  },
  en: {
    title: 'My Travel Route',
    saveBtn: 'Save',
    shareBtn: 'Share',
    noImage: 'No Image',
    deleteRoute: 'Delete route',
    toastSave: 'Travel route has been saved successfully.',
    toastShare: 'Share link has been copied to clipboard.',
    toastDelete: (name) => `'${name}' has been deleted from the route.`,
    noRouteTitle: (day) => `No route for Day ${day} yet`,
    noRouteDesc: 'Try adding places from the Search tab!'
  }
};

export default function TravelRouteTab({ showToast }) {
  const allDay = useTravelStore((state) => state.all_day);
  const travelPath = useTravelStore((state) => state.travelPath);
  const removePathItem = useTravelStore((state) => state.removePathItem);
  const selectedDay = useTravelStore((state) => state.selectedDay);
  const setSelectedDay = useTravelStore((state) => state.setSelectedDay);

  const lang = useLangStore((state) => state.lang);
  const t = UI_TEXT[lang];

  const days = Array.from({ length: allDay }, (_, i) => i + 1);

  let currentDay = selectedDay;
  if (selectedDay > allDay) {
    currentDay = 1;
    setSelectedDay(1);
  }

  const currentRoute = travelPath[currentDay] || [];

  return (
      <div className="flex-1 flex flex-col min-h-0 p-5 space-y-6">
        {/* 상단 타이틀 및 버튼 영역 */}
        <div className="flex items-center justify-between shrink-0">
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
            {t.title}
          </h2>
          <div className="flex gap-2">
            <button
                type="button"
                onClick={() => showToast(t.toastSave)}
                className="flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-3.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-all shadow-sm"
            >
              {t.saveBtn}
            </button>
            <button
                type="button"
                onClick={() => showToast(t.toastShare)}
                className="flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-3.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-all shadow-sm"
            >
              {t.shareBtn}
            </button>
          </div>
        </div>

        {/* Day 선택 Chip 영역 */}
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          {days.map((d) => (
              <button
                  key={d}
                  type="button"
                  onClick={() => setSelectedDay(d)}
                  className={`rounded-full px-5 py-2.5 text-sm font-semibold transition-all shadow-sm ${
                      currentDay === d
                          ? 'bg-blue-600 text-white border border-blue-600'
                          : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
                  }`}
              >
                Day {d}
              </button>
          ))}
        </div>

        {/* 루트 리스트 영역 */}
        <div className="flex-1 overflow-y-auto space-y-4 min-h-0 pr-1">
          {currentRoute.length > 0 ? (
              currentRoute.map((place, index) => {
                const category = getPlaceDisplayCategory(place);
                const subCategory = getPlaceDisplaySubCategory(place);
                const rating = getPlaceDisplayRating(place);
                const image = getPlaceDisplayImage(place);

                return (
                    <article
                        key={place.id}
                        // 변경 포인트: 상하 구조를 나누기 위해 flex-col 구조 사용
                        className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:border-slate-300 transition-all duration-200 relative"
                    >
                      {/* [상단 영역] 번호 + 이미지 + 텍스트 정보 */}
                      <div className="flex items-start gap-4">
                        {/* 왼쪽: 순서 번호와 썸네일 이미지 */}
                        <div className="flex items-center gap-3 shrink-0 mt-0.5">
                          <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold text-white shadow-sm">
                            {index + 1}
                          </div>

                          <div className="flex size-16 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-slate-100 bg-slate-50">
                            {image ? (
                                <img
                                    src={image}
                                    alt={place.name}
                                    className="h-full w-full object-cover"
                                />
                            ) : (
                                <span className="text-xs font-semibold text-slate-400">
                                  {t.noImage}
                                </span>
                            )}
                          </div>
                        </div>

                        {/* 오른쪽: 텍스트 정보 */}
                        <div className="flex-1 min-w-0 pr-8 space-y-1">
                          <div className="flex items-center gap-2">
                            <h3 className="font-bold text-slate-800 text-lg leading-snug truncate">
                              {place.name}
                            </h3>
                            <span
                                className={`text-[10px] font-bold px-1.5 py-0.5 rounded whitespace-nowrap shrink-0 ${
                                    category === '카페'
                                        ? 'text-orange-500 bg-orange-50'
                                        : category === '맛집'
                                            ? 'text-green-500 bg-green-50'
                                            : category === '숙소'
                                                ? 'text-purple-500 bg-purple-50'
                                                : category === '보관소'
                                                    ? 'text-cyan-500 bg-cyan-50'
                                                    : 'text-red-500 bg-red-50'
                                }`}
                            >
                              {subCategory}
                            </span>
                          </div>

                          <p className="text-sm text-slate-400 break-keep">
                            {place.address}
                          </p>

                          <p className="text-sm text-amber-500 font-semibold flex items-center gap-1 mt-0.5">
                            ★ {rating}
                          </p>
                        </div>
                      </div>

                      {/* [하단 전체 영역] 추천 이유 박스 (카드 내 가로폭 전체 확보) */}
                      {place.selectionReason && (
                          <div className="rounded-xl bg-slate-50 p-3.5 border border-slate-100 relative mt-1 mx-1">
                            {/*
                                말풍선 꼬리를 L7 명동 텍스트 시작 라인과 매칭되도록
                                left 오프셋 값을 left-[116px](번호7 + 갭12 + 이미지64 + 갭16 + 꼬리보정17)으로 세밀하게 조정
                            */}
                            <div
                                className="absolute top-0 left-[116px] -translate-y-[11px] w-4 h-3 bg-slate-50 border-t border-l border-slate-100"
                                style={{
                                  clipPath: 'polygon(50% 0%, 0% 100%, 100% 100%)',
                                }}
                            />
                            <p className="text-[13px] text-slate-600 leading-relaxed font-normal whitespace-pre-wrap break-keep relative z-10">
                              💡 {place.selectionReason}
                            </p>
                          </div>
                      )}

                      {/* [우측 상단] X자 삭제 버튼 */}
                      <div className="absolute top-4 right-4 z-10">
                        <button
                            type="button"
                            onClick={() => {
                              const targetDay = Number(currentDay);
                              removePathItem(targetDay, place.id);
                              showToast(t.toastDelete(place.name));
                            }}
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
              })
          ) : (
              <div className="flex flex-col items-center justify-center py-12 text-center border-2 border-dashed border-slate-100 rounded-2xl">
                <span className="text-3xl mb-2">📍</span>
                <p className="text-sm font-semibold text-slate-700">
                  {t.noRouteTitle(currentDay)}
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  {t.noRouteDesc}
                </p>
              </div>
          )}
        </div>
      </div>
  );
}