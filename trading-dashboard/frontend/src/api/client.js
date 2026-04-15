const BASE = '/api'

async function get(path) {
  const res = await fetch(BASE + path)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export const api = {
  health:        () => get('/health'),
  nseDashboard:  (limit = 50) => get(`/nse/dashboard?limit=${limit}`),
  nseInstrument: (symbol) => get(`/nse/instrument/${symbol}`),
  mcxDashboard:  () => get('/mcx/dashboard'),
  summary:       () => get('/summary'),
}
