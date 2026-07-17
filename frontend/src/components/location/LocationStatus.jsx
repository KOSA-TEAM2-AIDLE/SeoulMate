import { useCurrentLocation } from '../../hooks/location/useCurrentLocation';
import useLocationStore from '../../stores/useLocationStore';

export default function LocationStatus() {
  const status = useLocationStore((state) => state.status);
  const error = useLocationStore((state) => state.error);
  const { requestCurrentLocation } = useCurrentLocation(false);

  if (status === 'idle') {
    return null;
  }

  if (status === 'loading') {
    return (
      <div
        className="absolute right-4 top-4 z-20 rounded-lg border border-blue-100 bg-white px-4 py-3 text-sm font-medium text-blue-600 shadow-md"
        role="status"
      >
        현재 위치를 확인하고 있습니다.
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div
        className="absolute right-4 top-4 z-20 max-w-xs rounded-lg border border-red-200 bg-white p-4 shadow-md"
        role="alert"
      >
        <p className="text-sm font-semibold text-red-600">{error?.message}</p>
        <button
          type="button"
          className="mt-3 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700"
          onClick={requestCurrentLocation}
        >
          다시 시도
        </button>
      </div>
    );
  }

  return (
    <div
      className="absolute right-4 top-4 z-20 rounded-lg border border-emerald-200 bg-white px-4 py-3 text-sm font-medium text-emerald-700 shadow-md"
      role="status"
    >
      현재 위치를 확인했습니다.
    </div>
  );
}
