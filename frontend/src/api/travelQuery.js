const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

async function parseJsonResponse(response, fallbackMessage) {
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = payload?.detail;
    const message =
      typeof detail === 'string'
        ? detail
        : detail?.message ?? fallbackMessage;
    throw new Error(message);
  }

  return payload;
}

export async function startTravelQuery({
  message,
  language = 'ko',
  history = [],
  previousStructuredQuery,
  lat,
  lng,
}) {
  const response = await fetch(`${API_BASE_URL}/travel-query/start`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({
      message,
      language,
      reference_at: new Date().toISOString(),
      history,
      previous_structured_query: previousStructuredQuery,
      lat,
      lng,
    }),
  });

  return parseJsonResponse(response, '질문 분석에 실패했습니다.');
}

export async function resumeTravelQuery(threadId, answer, coordinates) {
  const response = await fetch(
    `${API_BASE_URL}/travel-query/${encodeURIComponent(threadId)}/resume`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        answer,
        lat: coordinates?.latitude,
        lng: coordinates?.longitude,
      }),
    },
  );

  return parseJsonResponse(response, '추가 답변 처리에 실패했습니다.');
}
