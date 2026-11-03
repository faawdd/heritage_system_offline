import { isCanceledRequest } from './networkRequest.js'

export function kmlRecordKey(row) {
  return `${row.id}|${row.updated_at || row.created_at || ''}`
}

export async function loadKmlRecords(records, { cache, fetchBatch, fetchSingle, signal, onResult }) {
  const pending = []
  const deliver = async (row, idx, text, error) => {
    if (signal?.aborted) return
    await onResult({ row, idx, text, error })
  }
  for (const [idx, row] of records.entries()) {
    if (signal?.aborted) return
    if (!Number.isInteger(Number(row.id)) || Number(row.id) <= 0) {
      await deliver(row, idx, '', new Error('无有效记录ID'))
    } else if (cache.has(kmlRecordKey(row))) {
      await deliver(row, idx, cache.get(kmlRecordKey(row)))
    } else {
      pending.push({ row, idx })
    }
  }

  const chunks = []
  for (let i = 0; i < pending.length; i += 4) chunks.push(pending.slice(i, i + 4))
  let cursor = 0
  const save = async ({ row, idx }, payload) => {
    const text = payload?.kml_text
    if (!text) throw new Error('KML 内容为空')
    if (signal?.aborted) return
    cache.set(kmlRecordKey(row), text)
    await deliver(row, idx, text)
  }
  const worker = async () => {
    while (cursor < chunks.length && !signal?.aborted) {
      const chunk = chunks[cursor++]
      let result
      try {
        result = await fetchBatch(chunk.map(({ row }) => row.id), { signal })
        if (!result?.success) throw new Error(result?.message || '批量加载失败')
      } catch (error) {
        if (isCanceledRequest(error) || signal?.aborted) return
        // Do not amplify a network failure into another round of individual downloads.
        if (![404, 405, 413].includes(error?.response?.status)) {
          for (const { row, idx } of chunk) await deliver(row, idx, '', error)
          continue
        }
      }
      const items = new Map((result?.data?.items || []).map((item) => [Number(item.record_id), item]))
      const failures = new Map((result?.data?.failed_items || []).map((item) => [Number(item.record_id), item.message]))
      for (const entry of chunk) {
        if (signal?.aborted) return
        try {
          const id = Number(entry.row.id)
          if (failures.has(id)) throw new Error(failures.get(id) || 'KML 解析失败')
          let payload = items.get(id)
          if (!payload) {
            const single = await fetchSingle(id, { signal })
            if (!single?.success) throw new Error(single?.message || 'KML 加载失败')
            payload = single.data
          }
          await save(entry, payload)
        } catch (error) {
          if (isCanceledRequest(error) || signal?.aborted) return
          await deliver(entry.row, entry.idx, '', error)
        }
      }
    }
  }
  await Promise.all(Array.from({ length: Math.min(2, chunks.length) }, worker))
}
