'use client'
import { useParams } from 'next/navigation'
import Link from 'next/link'

const PLATFORMS = [
  { id: 'spotify', name: 'Spotify', color: '#1DB954', icon: 'S', url: (v) => `https://open.spotify.com/artist/${v}` },
  { id: 'apple', name: 'Apple Music', color: '#FA2D48', icon: 'A', url: (v) => `https://music.apple.com/artist/${v}` },
  { id: 'youtube', name: 'YouTube Music', color: '#FF0000', icon: 'Y', url: (v) => `https://music.youtube.com/channel/${v}` },
  { id: 'soundcloud', name: 'SoundCloud', color: '#FF5500', icon: 'S', url: (v) => `https://soundcloud.com/${v}` },
  { id: 'tidal', name: 'Tidal', color: '#00FFFF', icon: 'T', url: (v) => `https://tidal.com/artist/${v}` },
  { id: 'bandcamp', name: 'Bandcamp', color: '#1DA0C3', icon: 'B', url: (v) => v.includes('.') ? `https://${v}` : `https://${v}.bandcamp.com` },
]

const DEMO_PERSONAS = {
  'yooj': {
    name: 'YOOJ',
    genre: 'K-Pop / R&B',
    color: '#7C3AED',
    bio: 'Korean-American R&B blending Seoul vibes with LA production.',
    links: { spotify: 'yooj-official', apple: 'yooj', soundcloud: 'yooj' },
    latestRelease: { title: 'Glass Heart EP', date: 'Aug 15, 2026' },
  },
  'nitefall': {
    name: 'nitefall',
    genre: 'Lo-fi / Ambient',
    color: '#3B82F6',
    bio: 'Late-night lo-fi for studying, sleeping, and staring at ceilings.',
    links: { spotify: 'nitefall-music', apple: 'nitefall', youtube: 'nitefall-lofi', soundcloud: 'nitefall', tidal: 'nitefall', bandcamp: 'nitefall.bandcamp.com' },
    latestRelease: { title: 'Midnight Rain', date: 'Aug 15, 2026' },
  },
  'ctrlv': {
    name: 'CTRL+V',
    genre: 'Hyperpop / Electronic',
    color: '#EC4899',
    bio: 'Chaotic energy, pitched vocals, and distorted everything.',
    links: { spotify: 'ctrlv-hyper', youtube: 'ctrlv-music', soundcloud: 'ctrlv' },
    latestRelease: { title: 'GLITCH.exe', date: 'Aug 22, 2026' },
  },
  'dr-groove': {
    name: 'Dr. Groove',
    genre: 'Jazz / Neo-Soul',
    color: '#10B981',
    bio: 'Smooth jazz meets modern neo-soul. Late nights, warm tones.',
    links: { spotify: 'dr-groove-jazz', apple: 'dr-groove', tidal: 'dr-groove' },
    latestRelease: { title: 'Late Night Sessions Vol. 3', date: 'Sep 1, 2026' },
  },
  'seoul-phantom': {
    name: 'Seoul Phantom',
    genre: 'K-Hip-Hop',
    color: '#EF4444',
    bio: '서울 유령 — underground Korean hip-hop from the shadows.',
    links: { youtube: 'seoul-phantom', soundcloud: 'seoul-phantom' },
    latestRelease: { title: '서울 유령 Mixtape', date: 'Sep 12, 2026' },
  },
  'glass-lake': {
    name: 'glass_lake',
    genre: 'Indie Folk / Acoustic',
    color: '#F59E0B',
    bio: 'Acoustic guitar, open fields, and words that land softly.',
    links: { spotify: 'glass-lake-folk', apple: 'glass-lake', soundcloud: 'glass-lake', bandcamp: 'glasslake.bandcamp.com' },
    latestRelease: null,
  },
}

export default function SmartLinkPage() {
  const params = useParams()
  const slug = params.slug
  const persona = DEMO_PERSONAS[slug]

  if (!persona) {
    return (
      <div className="min-h-screen bg-neutral-950 text-neutral-100 flex items-center justify-center px-5">
        <div className="text-center">
          <div className="text-4xl mb-4">🎵</div>
          <h1 className="text-xl font-bold mb-2">Artist not found</h1>
          <p className="text-sm text-neutral-500 mb-6">This link doesn't match any persona.</p>
          <Link href="/persona-hub" className="text-violet-400 text-sm hover:underline">Go to PersonaHub</Link>
        </div>
      </div>
    )
  }

  const connectedPlatforms = PLATFORMS.filter(p => persona.links[p.id])

  return (
    <div className="min-h-screen flex flex-col" style={{ background: `linear-gradient(180deg, ${persona.color}18 0%, #0a0a0a 40%)` }}>
      <div className="flex-1 flex flex-col items-center justify-center px-5 py-12">
        <div className="w-full max-w-sm">
          {/* Avatar */}
          <div className="text-center mb-8">
            <div
              className="w-24 h-24 rounded-2xl mx-auto mb-4 flex items-center justify-center text-white text-3xl font-bold shadow-2xl"
              style={{ background: persona.color, boxShadow: `0 8px 40px ${persona.color}40` }}
            >
              {persona.name[0]}
            </div>
            <h1 className="text-2xl font-bold tracking-tight">{persona.name}</h1>
            <p className="text-sm text-neutral-500 mt-1">{persona.genre}</p>
            {persona.bio && (
              <p className="text-sm text-neutral-400 mt-3 leading-relaxed max-w-xs mx-auto">{persona.bio}</p>
            )}
          </div>

          {/* Latest release */}
          {persona.latestRelease && (
            <div className="mb-6 bg-white/5 border border-white/10 rounded-xl p-4 text-center">
              <div className="text-[10px] font-semibold uppercase tracking-widest text-neutral-500 mb-1">Latest Release</div>
              <div className="font-semibold text-sm">{persona.latestRelease.title}</div>
              <div className="text-xs text-neutral-500 mt-0.5">{persona.latestRelease.date}</div>
            </div>
          )}

          {/* Platform links */}
          <div className="space-y-2.5">
            {connectedPlatforms.map(platform => (
              <a
                key={platform.id}
                href={platform.url(persona.links[platform.id])}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 w-full px-5 py-3.5 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition group"
              >
                <div
                  className="w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
                  style={{ background: platform.color }}
                >
                  {platform.icon}
                </div>
                <span className="font-medium text-sm flex-1">{platform.name}</span>
                <svg className="w-4 h-4 text-neutral-600 group-hover:text-neutral-300 transition" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            ))}
          </div>

          {connectedPlatforms.length === 0 && (
            <div className="text-center py-8">
              <p className="text-sm text-neutral-500">No streaming links configured yet.</p>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="text-center py-6">
        <Link href="/persona-hub" className="text-xs text-neutral-600 hover:text-neutral-400 transition">
          Powered by PersonaHub
        </Link>
      </div>
    </div>
  )
}
