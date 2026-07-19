const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export async function fetchTransitRoute(origin, destination, language = 'en') {
  const params = new URLSearchParams({ origin_lat: origin.lat, origin_lng: origin.lng, destination_lat: destination.lat, destination_lng: destination.lng, language });
  const response = await fetch(`${API_BASE_URL}/routes/transit?${params}`);
  if (!response.ok) throw new Error(`Transit route request failed (${response.status}).`);
  return response.json();
}

export async function fetchTransitGeometry(mapObject) {
  const response = await fetch(`${API_BASE_URL}/routes/transit/geometry?map_object=${encodeURIComponent(mapObject)}`);
  if (!response.ok) throw new Error(`Transit geometry request failed (${response.status}).`);
  return response.json();
}
