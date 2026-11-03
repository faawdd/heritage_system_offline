export const MAP_REQUEST_TIMEOUT = 60000
export const KML_ACTION_TIMEOUT = 10 * 60 * 1000

export function isCanceledRequest(error) {
  return error?.code === 'ERR_CANCELED' || error?.name === 'AbortError'
}

function waitForRetry(delay, signal) {
  return new Promise((resolve, reject) => {
    const cancel = () => {
      clearTimeout(timer)
      signal?.removeEventListener('abort', cancel)
      reject(new DOMException('Request canceled', 'AbortError'))
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', cancel)
      resolve()
    }, delay)
    signal?.addEventListener('abort', cancel, { once: true })
    if (signal?.aborted) cancel()
  })
}

// Only use for read-only operations, including the batch KML POST.
export async function requestMapData(request, { signal, retries = 2, retryDelay = 1000 } = {}) {
  for (let attempt = 0; ; attempt += 1) {
    if (signal?.aborted) throw new DOMException('Request canceled', 'AbortError')
    try {
      return await request()
    } catch (error) {
      const status = error?.response?.status
      const transient = status
        ? [408, 429, 502, 503, 504].includes(status)
        : ['ERR_NETWORK', 'ECONNABORTED', 'ETIMEDOUT'].includes(error?.code)
      if (isCanceledRequest(error) || !transient || attempt >= retries) throw error
      await waitForRetry(retryDelay * 2 ** attempt, signal)
    }
  }
}

export function networkErrorMessage(error, fallback) {
  if (['ECONNABORTED', 'ETIMEDOUT'].includes(error?.code)) {
    return '网络请求超时，请检查连接后重试'
  }
  if (error?.code === 'ERR_NETWORK') return '网络连接失败，请检查连接后重试'
  return error?.message || fallback
}
