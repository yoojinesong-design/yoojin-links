export const COLORS = ['#7C3AED', '#EC4899', '#F59E0B', '#10B981', '#3B82F6', '#EF4444', '#8B5CF6', '#06B6D4']

export const MOCK_PERSONAS = [
  { id: '1', name: 'YOOJ', genre: 'K-Pop / R&B', color: '#7C3AED', releases: 12, streams: 45200, revenue: 142.30, active: true },
  { id: '2', name: 'nitefall', genre: 'Lo-fi / Ambient', color: '#3B82F6', releases: 28, streams: 128400, revenue: 384.20, active: true },
  { id: '3', name: 'CTRL+V', genre: 'Hyperpop / Electronic', color: '#EC4899', releases: 8, streams: 22100, revenue: 67.80, active: true },
  { id: '4', name: 'Dr. Groove', genre: 'Jazz / Neo-Soul', color: '#10B981', releases: 15, streams: 61300, revenue: 198.50, active: true },
  { id: '5', name: 'Seoul Phantom', genre: 'K-Hip-Hop', color: '#EF4444', releases: 6, streams: 18700, revenue: 54.10, active: true },
  { id: '6', name: 'glass_lake', genre: 'Indie Folk / Acoustic', color: '#F59E0B', releases: 10, streams: 34500, revenue: 112.40, active: false },
]

export const MOCK_RELEASES = [
  { id: 'r1', persona: 'nitefall', personaColor: '#3B82F6', title: 'Midnight Rain', date: '2026-08-15', status: 'scheduled', type: 'single', aiGenerated: true },
  { id: 'r2', persona: 'YOOJ', personaColor: '#7C3AED', title: 'Glass Heart EP', date: '2026-08-15', status: 'draft', type: 'ep', aiGenerated: true },
  { id: 'r3', persona: 'CTRL+V', personaColor: '#EC4899', title: 'GLITCH.exe', date: '2026-08-22', status: 'scheduled', type: 'single', aiGenerated: true },
  { id: 'r4', persona: 'Dr. Groove', personaColor: '#10B981', title: 'Late Night Sessions Vol. 3', date: '2026-09-01', status: 'draft', type: 'album', aiGenerated: false },
  { id: 'r5', persona: 'Seoul Phantom', personaColor: '#EF4444', title: '서울 유령 Mixtape', date: '2026-09-12', status: 'idea', type: 'mixtape', aiGenerated: true },
  { id: 'r6', persona: 'nitefall', personaColor: '#3B82F6', title: 'Cloud Nine', date: '2026-08-29', status: 'scheduled', type: 'single', aiGenerated: true },
]

export const PLATFORMS = [
  { id: 'spotify', name: 'Spotify', color: '#1DB954', prefix: 'open.spotify.com/artist/' },
  { id: 'apple', name: 'Apple Music', color: '#FA2D48', prefix: 'music.apple.com/artist/' },
  { id: 'youtube', name: 'YouTube Music', color: '#FF0000', prefix: 'music.youtube.com/channel/' },
  { id: 'soundcloud', name: 'SoundCloud', color: '#FF5500', prefix: 'soundcloud.com/' },
  { id: 'tidal', name: 'Tidal', color: '#00FFFF', prefix: 'tidal.com/artist/' },
  { id: 'bandcamp', name: 'Bandcamp', color: '#1DA0C3', prefix: 'bandcamp.com' },
]

export const MOCK_LINKS = {
  '1': { spotify: 'yooj-official', apple: 'yooj', youtube: '', soundcloud: 'yooj', tidal: '', bandcamp: '' },
  '2': { spotify: 'nitefall-music', apple: 'nitefall', youtube: 'nitefall-lofi', soundcloud: 'nitefall', tidal: 'nitefall', bandcamp: 'nitefall.bandcamp.com' },
  '3': { spotify: 'ctrlv-hyper', apple: '', youtube: 'ctrlv-music', soundcloud: 'ctrlv', tidal: '', bandcamp: '' },
  '4': { spotify: 'dr-groove-jazz', apple: 'dr-groove', youtube: '', soundcloud: '', tidal: 'dr-groove', bandcamp: '' },
  '5': { spotify: '', apple: '', youtube: 'seoul-phantom', soundcloud: 'seoul-phantom', tidal: '', bandcamp: '' },
  '6': { spotify: 'glass-lake-folk', apple: 'glass-lake', youtube: '', soundcloud: 'glass-lake', tidal: '', bandcamp: 'glasslake.bandcamp.com' },
}

export const STATUS_STYLE = {
  scheduled: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  draft: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  idea: 'bg-neutral-500/15 text-neutral-400 border-neutral-500/30',
  released: 'bg-violet-500/15 text-violet-400 border-violet-500/30',
}

export const MONTHS = ['Aug 2026', 'Sep 2026', 'Oct 2026']

export const MOCK_PLATFORM_STREAMS = [
  { platform: 'Spotify', streams: 182400, pct: 59, color: '#1DB954' },
  { platform: 'Apple Music', streams: 52100, pct: 17, color: '#FA2D48' },
  { platform: 'YouTube Music', streams: 37200, pct: 12, color: '#FF0000' },
  { platform: 'SoundCloud', streams: 21800, pct: 7, color: '#FF5500' },
  { platform: 'Tidal', streams: 9400, pct: 3, color: '#00FFFF' },
  { platform: 'Other', streams: 7300, pct: 2, color: '#6B7280' },
]

export const MOCK_MONTHLY_GROWTH = [
  { month: 'Mar', streams: 18200, revenue: 54.60 },
  { month: 'Apr', streams: 24100, revenue: 72.30 },
  { month: 'May', streams: 31400, revenue: 94.20 },
  { month: 'Jun', streams: 42800, revenue: 128.40 },
  { month: 'Jul', streams: 58600, revenue: 175.80 },
  { month: 'Aug', streams: 62300, revenue: 186.90 },
]

export const MOCK_TOP_TRACKS = [
  { title: '3am in Gangnam', persona: 'nitefall', personaColor: '#3B82F6', streams: 34200, revenue: 102.60 },
  { title: 'Velvet Underground', persona: 'Dr. Groove', personaColor: '#10B981', streams: 28100, revenue: 84.30 },
  { title: 'Glass Heart', persona: 'YOOJ', personaColor: '#7C3AED', streams: 22400, revenue: 67.20 },
  { title: 'CTRL+DELETE', persona: 'CTRL+V', personaColor: '#EC4899', streams: 18700, revenue: 56.10 },
  { title: 'Rain on Concrete', persona: 'nitefall', personaColor: '#3B82F6', streams: 16300, revenue: 48.90 },
  { title: 'Seoul After Dark', persona: 'Seoul Phantom', personaColor: '#EF4444', streams: 14800, revenue: 44.40 },
  { title: 'Autumn Leaves', persona: 'glass_lake', personaColor: '#F59E0B', streams: 12100, revenue: 36.30 },
  { title: 'Moonlight Sonata (remix)', persona: 'Dr. Groove', personaColor: '#10B981', streams: 11400, revenue: 34.20 },
]

export const MOCK_GEO = [
  { country: 'United States', pct: 38, streams: 117400 },
  { country: 'South Korea', pct: 22, streams: 68000 },
  { country: 'Japan', pct: 12, streams: 37100 },
  { country: 'United Kingdom', pct: 8, streams: 24700 },
  { country: 'Germany', pct: 5, streams: 15500 },
  { country: 'Others', pct: 15, streams: 47500 },
]
