import useTravelRoute from '../../hooks/sidebar/useTravelRoute';
import RouteItem from './RouteItem';

export default function TravelRouteTab({ showToast }) {
  const {
    t,
    days,
    currentDay,
    currentRoute,
    setSelectedDay,
    handleDeleteItem,
    handleSavePDF,
    handleSharePDF
  } = useTravelRoute(showToast);

  return (
      <div className="flex-1 flex flex-col min-h-0 p-5 space-y-6">
        {/* 최상단 헤더 및 전체 저장/공유 컨트롤 */}
        <div className="flex items-center justify-between shrink-0">
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
            {t.title}
          </h2>
          <div className="flex gap-2">
            <button
                type="button"
                onClick={handleSavePDF}
                className="flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-3.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-all shadow-sm"
            >
              {t.saveBtn}
            </button>
            <button
                type="button"
                onClick={handleSharePDF}
                className="flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-3.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-all shadow-sm"
            >
              {t.shareBtn}
            </button>
          </div>
        </div>

        {/* 일차 이동 탭 버튼들 */}
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

        {/* 루트 리스트 바디 */}
        <div className="flex-1 overflow-y-auto space-y-4 min-h-0 pr-1">
          {currentRoute.length > 0 ? (
              currentRoute.map((place, index) => (
                  <RouteItem
                      key={place.id}
                      place={place}
                      index={index}
                      onDelete={handleDeleteItem}
                      t={t}
                  />
              ))
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