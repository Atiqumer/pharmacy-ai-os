const RETRYABLE_STATUS = new Set([408, 425, 429, 500, 502, 503, 504]);

const pause = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

export async function fetchWithRetry(authFetch, url, options = {}, retries = 2) {
  const method = (options.method || 'GET').toUpperCase();
  if (method !== 'GET') return authFetch(url, options);

  let lastError;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const response = await authFetch(url, options);
      if (!RETRYABLE_STATUS.has(response.status) || attempt === retries) return response;
      lastError = new Error(`Request failed with status ${response.status}`);
    } catch (error) {
      lastError = error;
      if (attempt === retries) throw error;
    }

    await pause(400 * (attempt + 1));
  }

  throw lastError || new Error('Request failed');
}
