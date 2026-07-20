const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

function parseServerEvent(eventText) {
  const dataLines = eventText
    .split('\n')
    .filter((line) => line.startsWith('data: '))
    .map((line) => line.slice(6));

  if (dataLines.length === 0) {
    return null;
  }

  return JSON.parse(dataLines.join('\n'));
}

export async function streamChat({
  message,
  history = [],
  lang = 'ko',
  parsedIntent,
  sourceMode,
  parsedQuery,
  lat,
  lng,
  onMeta,
  onToken,
  onDone,
  onError,
}) {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify({
      message,
      history,
      lang,
      parsed_intent: parsedIntent,
      source_mode: sourceMode,
      parsed_query: parsedQuery,
      lat,
      lng,
    }),
  });

  if (!response.ok) {
    throw new Error(`채팅 요청에 실패했습니다. (${response.status})`);
  }

  if (!response.body) {
    throw new Error('채팅 응답 스트림을 읽을 수 없습니다.');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();

    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split('\n\n');
    buffer = events.pop() ?? '';

    for (const eventText of events) {
      const payload = parseServerEvent(eventText);

      if (!payload) {
        continue;
      }

      if (payload.type === 'meta') {
        onMeta?.(payload);
      }

      if (payload.type === 'token') {
        onToken?.(payload.text ?? '');
      }

      if (payload.type === 'done') {
        onDone?.(payload);
      }

      if (payload.type === 'error') {
        onError?.(payload);
      }
    }
  }

  if (buffer.trim()) {
    const payload = parseServerEvent(buffer);

    if (payload?.type === 'token') {
      onToken?.(payload.text ?? '');
    }
  }
}
