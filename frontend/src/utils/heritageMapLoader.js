export async function loadHeritageMapData({ fetchPage, signal, geometry = 'none', onPoints, onGeometry }) {
  const rows = []
  let legacy = false
  async function pages(view, consume) {
    let next = 0
    do {
      if (signal?.aborted) throw new DOMException('Request canceled', 'AbortError')
      const result = await fetchPage(view, next, signal)
      if (!result?.success || !Array.isArray(result.rows)) {
        throw new Error(result?.message || '文物地图数据格式错误')
      }
      if (signal?.aborted) throw new DOMException('Request canceled', 'AbortError')
      consume(result.rows)
      if (!Object.prototype.hasOwnProperty.call(result, 'next_cursor')) {
        legacy = true
        return
      }
      const current = next
      next = result.next_cursor
      if (next !== null && (!Number.isSafeInteger(next) || next <= current)) {
        throw new Error('文物地图数据分页游标无效')
      }
    } while (next !== null)
  }

  await pages('points', (page) => rows.push(...page))
  if (onPoints) onPoints(rows.slice())
  if (geometry !== 'none' && !legacy) {
    const pointsById = new Map(rows.map((row) => [row.id, row]))
    await pages(geometry, (page) => {
      for (const boundary of page) {
        const row = pointsById.get(boundary.id)
        if (row) Object.assign(row, boundary)
      }
      if (onGeometry) onGeometry(page)
    })
  } else if (legacy && onGeometry) {
    onGeometry(rows)
  }
  return { success: true, rows }
}
