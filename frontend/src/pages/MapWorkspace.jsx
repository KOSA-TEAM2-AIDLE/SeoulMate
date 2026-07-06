export default function MapWorkspace() {
  return (
    <section className="relative min-h-[460px] overflow-hidden bg-blue-50">
      <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(37,99,235,0.12)_1px,transparent_1px),linear-gradient(rgba(37,99,235,0.12)_1px,transparent_1px)] bg-[size:48px_48px]" />

      <div className="absolute inset-0 flex items-center justify-center">
        <div className="rounded-full border-4 border-blue-600 px-8 py-4 text-lg font-bold text-blue-700">
          지도 영역
        </div>
      </div>

      <div className="absolute right-4 top-4 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <button type="button" className="block px-4 py-3 text-xl font-semibold text-slate-700">
          +
        </button>
        <button type="button" className="block border-t border-slate-200 px-4 py-3 text-xl font-semibold text-slate-700">
          -
        </button>
      </div>

      <div className="absolute bottom-5 left-1/2 w-[min(520px,calc(100%-40px))] -translate-x-1/2 rounded-xl border border-slate-200 bg-white p-4 shadow-lg">
        <p className="text-sm font-semibold text-blue-600">선택된 장소 정보 카드</p>
        <p className="mt-1 text-sm text-slate-500">추후 지도 연동 후 상세 정보를 표시합니다.</p>
      </div>
    </section>
  );
}
