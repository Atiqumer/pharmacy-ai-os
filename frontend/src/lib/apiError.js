export function getApiErrorMessage(payload, fallback = 'Request failed') {
  const detail = payload?.detail;

  if (typeof detail === 'string' && detail.trim()) return detail;

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === 'string') return item;
        if (typeof item?.msg === 'string') return item.msg;
        return null;
      })
      .filter(Boolean);

    if (messages.length) return messages.join(', ');
  }

  if (detail && typeof detail === 'object') {
    if (typeof detail.message === 'string') return detail.message;
    return JSON.stringify(detail);
  }

  return fallback;
}
