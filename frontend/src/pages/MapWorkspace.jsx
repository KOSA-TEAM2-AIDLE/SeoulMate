import KakaoMap from '../components/map/KakaoMap';
import LocationStatus from '../components/location/LocationStatus';
import useTravelStore from '../stores/useTravelStore';

export default function MapWorkspace() {
    const selectedDay = useTravelStore((state) => state.selectedDay);
    const travelPath = useTravelStore((state) => state.travelPath);

    const routePlaces = travelPath[selectedDay] || [];

    return (
        <section className="relative min-h-[460px] overflow-hidden bg-blue-50">
            <KakaoMap places={routePlaces} />
            <LocationStatus />
            <div className="absolute z-10 bottom-5 left-1/2 w-[min(520px,calc(100%-40px))] -translate-x-1/2 rounded-xl border border-slate-200 bg-white p-4 shadow-lg">
                <p className="text-sm font-semibold text-blue-600">선택된 장소 정보 카드</p>
                <p className="mt-1 text-sm text-slate-500">
                    현재 표시 중인 장소 수: {routePlaces.length}
                </p>
            </div>
        </section>
    );
}