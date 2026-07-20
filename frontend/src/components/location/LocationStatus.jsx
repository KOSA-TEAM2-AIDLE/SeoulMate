import { useCurrentLocation } from '../../hooks/location/useCurrentLocation';
import useLocationStore from '../../stores/useLocationStore';

export default function LocationStatus() {
  const status = useLocationStore((state) => state.status);
  const error = useLocationStore((state) => state.error);
  const { requestCurrentLocation } = useCurrentLocation(false);

  if (status === 'idle') {
    return null;
  }

  if (status === 'error') {
    return (
      <button
        type="button"
        className="absolute right-4 top-4 z-20 size-4 rounded-full border-2 border-white bg-red-500 shadow-md transition-transform hover:scale-125 focus:outline-none focus:ring-2 focus:ring-red-400 focus:ring-offset-2"
        onClick={requestCurrentLocation}
        title={`${error?.message ?? '위치 정보를 확인하지 못했습니다.'} 다시 시도하려면 클릭하세요.`}
        aria-label={`${error?.message ?? '위치 정보를 확인하지 못했습니다.'} 다시 시도`}
      />
    );
  }

  if (status === 'loading') {
    return (
      <span
        className="absolute right-4 top-4 z-20 size-4 animate-pulse rounded-full border-2 border-white bg-blue-500 shadow-md"
        role="status"
        title="현재 위치를 확인하고 있습니다."
        aria-label="현재 위치 확인 중"
      />
    );
  }

  return (
    <span
      className="absolute right-4 top-4 z-20 size-4 rounded-full border-2 border-white bg-emerald-500 shadow-md"
      role="status"
      title="현재 위치를 확인했습니다."
      aria-label="현재 위치 확인 완료"
    />
  );
}
