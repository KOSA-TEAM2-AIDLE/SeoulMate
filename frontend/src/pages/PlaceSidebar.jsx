const PLACE_FILTERS = ['전체', '명소', '맛집', '카페', '숙소'];
const PLACE_ITEMS = ['경복궁', '북촌 한옥마을', '익선동 카페거리'];

export default function PlaceSidebar() {
  return (
    <aside className="flex min-h-[360px] flex-col border-r border-slate-200 bg-white">
      <nav className="grid grid-cols-2 border-b border-slate-200 text-sm font-semibold">
        <button type="button" className="border-b-2 border-blue-600 px-4 py-4 text-blue-600">
          장소 검색
        </button>
        <button type="button" className="px-4 py-4 text-slate-500">
          내 여행 루트
        </button>
      </nav>

      <div className="space-y-5 overflow-y-auto p-5">
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-500">
          장소, 키워드 검색
        </div>

        <div className="flex flex-wrap gap-2">
          {PLACE_FILTERS.map((filter, index) => (
            <span
              key={filter}
              className={`rounded-full border px-3 py-1 text-sm font-medium ${
                index === 0
                  ? 'border-blue-600 bg-blue-600 text-white'
                  : 'border-slate-200 text-slate-600'
              }`}
            >
              {filter}
            </span>
          ))}
        </div>

        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold">검색 결과</h2>
            <span className="text-sm text-slate-500">placeholder</span>
          </div>

          {PLACE_ITEMS.map((place) => (
            <article key={place} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex gap-3">
                <div className="size-16 rounded-lg bg-slate-200" />
                <div>
                  <h3 className="font-bold">{place}</h3>
                  <p className="mt-1 text-sm text-slate-500">장소 카드 영역</p>
                  <p className="mt-2 text-sm text-amber-500">별점 및 운영시간</p>
                </div>
              </div>
            </article>
          ))}
        </section>
      </div>
    </aside>
  );
}
