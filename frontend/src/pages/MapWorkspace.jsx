import KakaoMap from '../components/map/KakaoMap';

export default function MapWorkspace() {
  return (
    <section className="relative min-h-[460px] overflow-hidden bg-blue-50">
      <KakaoMap />

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