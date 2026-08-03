export function parseDistroKidCSV(text) {
  const lines = text.trim().split('\n')
  if (lines.length < 2) return []

  const headers = lines[0].split(',').map(h => h.trim().toLowerCase().replace(/['"]/g, ''))

  const artistIdx = headers.findIndex(h => h.includes('artist') || h.includes('name'))
  const titleIdx = headers.findIndex(h => h.includes('title') || h.includes('song') || h.includes('track'))
  const earningsIdx = headers.findIndex(h => h.includes('earning') || h.includes('revenue') || h.includes('amount') || h.includes('net'))
  const streamsIdx = headers.findIndex(h => h.includes('stream') || h.includes('quantity') || h.includes('plays'))
  const storeIdx = headers.findIndex(h => h.includes('store') || h.includes('platform') || h.includes('service'))
  const dateIdx = headers.findIndex(h => h.includes('date') || h.includes('period') || h.includes('month') || h.includes('reporting'))

  if (artistIdx === -1 || earningsIdx === -1) return []

  const entries = []
  for (let i = 1; i < lines.length; i++) {
    const cols = parseCSVLine(lines[i])
    if (cols.length <= Math.max(artistIdx, earningsIdx)) continue

    const revenue = parseFloat(cols[earningsIdx]?.replace(/[^0-9.-]/g, ''))
    if (isNaN(revenue)) continue

    entries.push({
      artist: cols[artistIdx]?.trim() || '',
      track_title: titleIdx >= 0 ? cols[titleIdx]?.trim() : '',
      revenue_usd: revenue,
      streams: streamsIdx >= 0 ? parseInt(cols[streamsIdx]?.replace(/[^0-9]/g, '')) || 0 : 0,
      platform: storeIdx >= 0 ? cols[storeIdx]?.trim() : '',
      period: dateIdx >= 0 ? cols[dateIdx]?.trim() : '',
    })
  }

  return entries
}

function parseCSVLine(line) {
  const result = []
  let current = ''
  let inQuotes = false

  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (ch === '"') {
      inQuotes = !inQuotes
    } else if (ch === ',' && !inQuotes) {
      result.push(current)
      current = ''
    } else {
      current += ch
    }
  }
  result.push(current)
  return result
}

export function matchToPersonas(entries, personas) {
  const matched = new Map()

  for (const p of personas) {
    matched.set(p.id, { persona: p, entries: [], totalRevenue: 0, totalStreams: 0 })
  }
  matched.set('unmatched', { persona: null, entries: [], totalRevenue: 0, totalStreams: 0 })

  for (const entry of entries) {
    const artistLower = entry.artist.toLowerCase()
    const match = personas.find(p => p.name.toLowerCase() === artistLower)

    const key = match ? match.id : 'unmatched'
    const bucket = matched.get(key)
    bucket.entries.push(entry)
    bucket.totalRevenue += entry.revenue_usd
    bucket.totalStreams += entry.streams
  }

  return Object.fromEntries(matched)
}
