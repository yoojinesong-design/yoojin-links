'use client'
import { useState, useRef, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { parseDistroKidCSV, matchToPersonas } from '../../../lib/csv-parser'
import { getSupabase } from '../../../lib/supabase-browser'
import {
  COLORS, MOCK_PERSONAS, MOCK_RELEASES, PLATFORMS, MOCK_LINKS,
  STATUS_STYLE, MONTHS, MOCK_PLATFORM_STREAMS, MOCK_MONTHLY_GROWTH,
  MOCK_TOP_TRACKS, MOCK_GEO,
} from '../../../lib/persona-hub-data'

function PersonaCard({ persona, onEdit }) {
  return (
    <div className="bg-neutral-900/60 border border-neutral-800/60 rounded-xl p-4 hover:border-neutral-700/60 transition group cursor-pointer" onClick={() => onEdit?.(persona)}>
      <div className="flex items-center gap-3 mb-3">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold" style={{ background: persona.color }}>{persona.name[0]}</div>
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-sm truncate">{persona.name}</div>
          <div className="text-xs text-neutral-500">{persona.genre}</div>
        </div>
        {!persona.active && <span className="text-[10px] uppercase tracking-wider text-neutral-600 font-semibold">Inactive</span>}
      </div>
      <div className="grid grid-cols-3 gap-2">
        <div><div className="text-lg font-bold tabular-nums">{persona.releases}</div><div className="text-[10px] text-neutral-500 uppercase tracking-wider">Releases</div></div>
        <div><div className="text-lg font-bold tabular-nums">{(persona.streams / 1000).toFixed(1)}K</div><div className="text-[10px] text-neutral-500 uppercase tracking-wider">Streams</div></div>
        <div><div className="text-lg font-bold tabular-nums text-emerald-400">${persona.revenue.toFixed(0)}</div><div className="text-[10px] text-neutral-500 uppercase tracking-wider">Revenue</div></div>
      </div>
    </div>
  )
}

function ReleaseRow({ release, allReleases, onClick }) {
  const hasCollision = allReleases.filter(r => r.date === release.date && r.id !== release.id).length > 0
  return (
    <div className={`flex items-center gap-3 py-3 border-b border-neutral-800/40 last:border-b-0 group ${release.aiGenerated ? 'cursor-pointer hover:bg-neutral-800/30' : ''}`} onClick={onClick}>
      <div className="w-1 h-8 rounded-full" style={{ background: release.personaColor }} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm truncate">{release.title}</span>
          {hasCollision && <span className="text-[10px] bg-red-500/15 text-red-400 border border-red-500/30 px-1.5 py-0.5 rounded font-semibold uppercase tracking-wider">Collision</span>}
          {release.aiGenerated && <span className="text-[10px] bg-violet-500/15 text-violet-400 border border-violet-500/30 px-1.5 py-0.5 rounded font-semibold uppercase tracking-wider">AI</span>}
        </div>
        <div className="text-xs text-neutral-500">{release.persona} · {release.type}</div>
      </div>
      <div className="text-right flex-shrink-0">
        <div className="text-xs tabular-nums text-neutral-400">{release.date}</div>
        <span className={`text-[10px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded border ${STATUS_STYLE[release.status]}`}>{release.status}</span>
      </div>
    </div>
  )
}

function AddPersonaModal({ onClose, onAdd }) {
  const [name, setName] = useState('')
  const [genre, setGenre] = useState('')
  const [color, setColor] = useState(COLORS[0])
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-neutral-900 border border-neutral-700 rounded-2xl p-6 w-full max-w-md mx-4 shadow-2xl" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-bold mb-4">Add New Persona</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1.5">Artist Name</label>
            <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. nitefall" className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2.5 text-sm text-neutral-100 placeholder:text-neutral-600 focus:outline-none focus:border-violet-500 transition" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1.5">Genre</label>
            <input type="text" value={genre} onChange={e => setGenre(e.target.value)} placeholder="e.g. Lo-fi / Ambient" className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2.5 text-sm text-neutral-100 placeholder:text-neutral-600 focus:outline-none focus:border-violet-500 transition" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1.5">Color</label>
            <div className="flex gap-2">{COLORS.map(c => (<button key={c} onClick={() => setColor(c)} className={`w-8 h-8 rounded-lg transition ${color === c ? 'ring-2 ring-white ring-offset-2 ring-offset-neutral-900' : 'hover:scale-110'}`} style={{ background: c }} />))}</div>
          </div>
        </div>
        <div className="flex gap-3 mt-6">
          <button onClick={onClose} className="flex-1 border border-neutral-700 text-neutral-300 py-2.5 rounded-lg text-sm font-medium hover:bg-neutral-800 transition">Cancel</button>
          <button onClick={() => { onAdd({ name, genre, color }); onClose() }} disabled={!name} className="flex-1 bg-violet-500 hover:bg-violet-400 disabled:opacity-40 disabled:hover:bg-violet-500 text-white py-2.5 rounded-lg text-sm font-semibold transition">Create Persona</button>
        </div>
      </div>
    </div>
  )
}

function EditPersonaModal({ persona, onClose, onSave, onToggleActive }) {
  const [name, setName] = useState(persona.name)
  const [genre, setGenre] = useState(persona.genre)
  const [color, setColor] = useState(persona.color)
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-neutral-900 border border-neutral-700 rounded-2xl p-6 w-full max-w-md mx-4 shadow-2xl" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-bold mb-4">Edit Persona</h3>
        <div className="space-y-4">
          <div><label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1.5">Artist Name</label><input type="text" value={name} onChange={e => setName(e.target.value)} className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2.5 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 transition" /></div>
          <div><label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1.5">Genre</label><input type="text" value={genre} onChange={e => setGenre(e.target.value)} className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2.5 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 transition" /></div>
          <div><label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1.5">Color</label><div className="flex gap-2">{COLORS.map(c => (<button key={c} onClick={() => setColor(c)} className={`w-8 h-8 rounded-lg transition ${color === c ? 'ring-2 ring-white ring-offset-2 ring-offset-neutral-900' : 'hover:scale-110'}`} style={{ background: c }} />))}</div></div>
        </div>
        <div className="flex gap-3 mt-6">
          <button onClick={() => { onToggleActive(persona.id); onClose() }} className={`text-xs px-3 py-2 rounded-lg border transition ${persona.active ? 'border-amber-500/30 text-amber-400 hover:bg-amber-500/10' : 'border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10'}`}>{persona.active ? 'Deactivate' : 'Activate'}</button>
          <div className="flex-1" />
          <button onClick={onClose} className="border border-neutral-700 text-neutral-300 px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-neutral-800 transition">Cancel</button>
          <button onClick={() => { onSave(persona.id, { name, genre, color }); onClose() }} disabled={!name} className="bg-violet-500 hover:bg-violet-400 disabled:opacity-40 text-white px-4 py-2.5 rounded-lg text-sm font-semibold transition">Save</button>
        </div>
      </div>
    </div>
  )
}

function AIChecklistModal({ release, onClose }) {
  const [checks, setChecks] = useState({ ddexAi: false, ddexComponent: false, ddexTraining: false, euArticle50: false, c2pa: false, spotifyCredit: false })
  const toggle = (key) => setChecks(prev => ({ ...prev, [key]: !prev[key] }))
  const completed = Object.values(checks).filter(Boolean).length
  const total = Object.keys(checks).length
  const items = [
    { key: 'ddexAi', label: 'DDEX IsAIGenerated', desc: 'Mark the release as AI-generated in your distributor metadata' },
    { key: 'ddexComponent', label: 'DDEX AIComponentType', desc: 'Specify: vocal, instrumental, lyrics, melody, or full composition' },
    { key: 'ddexTraining', label: 'DDEX AITrainingDisclosure', desc: 'Disclose AI model used (Suno, Udio, custom) and training data source' },
    { key: 'euArticle50', label: 'EU AI Act Article 50', desc: 'Machine-readable AI content marking present — required since Aug 2, 2026' },
    { key: 'c2pa', label: 'C2PA Watermark', desc: 'Verify C2PA/SynthID watermark is embedded in audio file' },
    { key: 'spotifyCredit', label: 'Spotify AI Credit', desc: 'Opt into Spotify AI Credits beta via DistroKid (recommended, not required)' },
  ]
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-neutral-900 border border-neutral-700 rounded-2xl p-6 w-full max-w-lg mx-4 shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-1"><h3 className="text-lg font-bold">AI Disclosure Checklist</h3><span className="text-xs font-mono text-violet-400">{completed}/{total}</span></div>
        <p className="text-xs text-neutral-500 mb-5">"{release.title}" by {release.persona}</p>
        <div className="space-y-2.5">
          {items.map(item => (
            <button key={item.key} onClick={() => toggle(item.key)} className={`w-full flex items-start gap-3 p-3 rounded-lg border transition text-left ${checks[item.key] ? 'bg-violet-500/10 border-violet-500/30' : 'bg-neutral-800/50 border-neutral-700/60 hover:bg-neutral-800'}`}>
              <div className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 mt-0.5 transition ${checks[item.key] ? 'bg-violet-500 border-violet-500' : 'border-neutral-600'}`}>{checks[item.key] && <span className="text-white text-xs">✓</span>}</div>
              <div><div className={`text-sm font-medium ${checks[item.key] ? 'text-violet-300' : 'text-neutral-200'}`}>{item.label}</div><div className="text-xs text-neutral-500 mt-0.5">{item.desc}</div></div>
            </button>
          ))}
        </div>
        <div className="mt-5 flex gap-3">
          <button onClick={onClose} className="flex-1 border border-neutral-700 text-neutral-300 py-2.5 rounded-lg text-sm font-medium hover:bg-neutral-800 transition">Close</button>
          <button className={`flex-1 py-2.5 rounded-lg text-sm font-semibold transition ${completed === total ? 'bg-emerald-500 hover:bg-emerald-400 text-white' : 'bg-violet-500 hover:bg-violet-400 text-white'}`}>{completed === total ? 'All Clear ✓' : `${total - completed} remaining`}</button>
        </div>
      </div>
    </div>
  )
}

function CSVUploadModal({ onClose, personas, onImport }) {
  const fileRef = useRef(null)
  const [csvData, setCsvData] = useState(null)
  const [matched, setMatched] = useState(null)
  const [error, setError] = useState('')
  const [fileName, setFileName] = useState('')
  const handleFile = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setFileName(file.name); setError('')
    const reader = new FileReader()
    reader.onload = (ev) => {
      const text = ev.target?.result
      const entries = parseDistroKidCSV(text)
      if (entries.length === 0) { setError('Could not parse CSV. Make sure it has Artist and Earnings columns.'); return }
      setCsvData(entries)
      setMatched(matchToPersonas(entries, personas))
    }
    reader.readAsText(file)
  }
  const totalRevenue = csvData?.reduce((s, e) => s + e.revenue_usd, 0) || 0
  const totalStreams = csvData?.reduce((s, e) => s + e.streams, 0) || 0
  const matchedEntries = matched ? Object.entries(matched).filter(([k]) => k !== 'unmatched') : []
  const unmatchedData = matched?.unmatched
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-neutral-900 border border-neutral-700 rounded-2xl p-6 w-full max-w-lg mx-4 shadow-2xl max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-bold mb-4">Import Revenue CSV</h3>
        {!csvData ? (
          <div className="space-y-4">
            <div className="border-2 border-dashed border-neutral-700 rounded-xl p-8 text-center cursor-pointer hover:border-violet-500/50 transition" onClick={() => fileRef.current?.click()}>
              <div className="text-3xl mb-2">📄</div>
              <p className="text-sm text-neutral-400">Drop your DistroKid/TuneCore CSV here</p>
              <p className="text-xs text-neutral-600 mt-1">or click to browse</p>
            </div>
            <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={handleFile} />
            {error && <p className="text-red-400 text-sm">{error}</p>}
            <div className="bg-neutral-800/50 border border-neutral-700/60 rounded-lg p-4">
              <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-2">Supported formats</p>
              <ul className="space-y-1 text-xs text-neutral-500"><li>DistroKid Bank/Stats CSV export</li><li>TuneCore Earnings Report CSV</li><li>Any CSV with Artist + Earnings columns</li></ul>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-3 flex items-center gap-3">
              <span className="text-emerald-400 text-lg">✓</span>
              <div><div className="text-sm font-medium text-emerald-300">{fileName}</div><div className="text-xs text-neutral-400">{csvData.length} entries · ${totalRevenue.toFixed(2)} total · {totalStreams.toLocaleString()} streams</div></div>
            </div>
            <div>
              <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-2">Matched to Personas</p>
              <div className="space-y-1.5">
                {matchedEntries.filter(([, v]) => v.entries.length > 0).sort((a, b) => b[1].totalRevenue - a[1].totalRevenue).map(([key, data]) => (
                  <div key={key} className="flex items-center gap-2 bg-neutral-800/50 rounded-lg p-2.5">
                    <div className="w-3 h-3 rounded" style={{ background: data.persona.color }} />
                    <span className="text-sm font-medium flex-1">{data.persona.name}</span>
                    <span className="text-xs text-neutral-500">{data.entries.length} tracks</span>
                    <span className="text-xs font-mono text-emerald-400 tabular-nums">${data.totalRevenue.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
            {unmatchedData?.entries.length > 0 && (
              <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
                <p className="text-xs font-semibold text-amber-400 mb-1">{unmatchedData.entries.length} unmatched entries</p>
                <p className="text-xs text-neutral-500">Artists not matching any persona: {[...new Set(unmatchedData.entries.map(e => e.artist))].slice(0, 5).join(', ')}{[...new Set(unmatchedData.entries.map(e => e.artist))].length > 5 && '...'}</p>
              </div>
            )}
            <div className="flex gap-3">
              <button onClick={onClose} className="flex-1 border border-neutral-700 text-neutral-300 py-2.5 rounded-lg text-sm font-medium hover:bg-neutral-800 transition">Cancel</button>
              <button onClick={() => { onImport(matched); onClose() }} className="flex-1 bg-violet-500 hover:bg-violet-400 text-white py-2.5 rounded-lg text-sm font-semibold transition">Import {csvData.length} entries</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function AddReleaseModal({ onClose, onAdd, personas }) {
  const [title, setTitle] = useState('')
  const [personaId, setPersonaId] = useState(personas[0]?.id || '')
  const [date, setDate] = useState('')
  const [type, setType] = useState('single')
  const [aiGenerated, setAiGenerated] = useState(true)
  const selectedPersona = personas.find(p => p.id === personaId)
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-neutral-900 border border-neutral-700 rounded-2xl p-6 w-full max-w-md mx-4 shadow-2xl" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-bold mb-4">New Release</h3>
        <div className="space-y-4">
          <div><label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1.5">Title</label><input type="text" value={title} onChange={e => setTitle(e.target.value)} placeholder="e.g. Midnight Rain" className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2.5 text-sm text-neutral-100 placeholder:text-neutral-600 focus:outline-none focus:border-violet-500 transition" /></div>
          <div><label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1.5">Persona</label><select value={personaId} onChange={e => setPersonaId(e.target.value)} className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2.5 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 transition">{personas.filter(p => p.active).map(p => (<option key={p.id} value={p.id}>{p.name}</option>))}</select></div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1.5">Release Date</label><input type="date" value={date} onChange={e => setDate(e.target.value)} className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2.5 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 transition" /></div>
            <div><label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1.5">Type</label><select value={type} onChange={e => setType(e.target.value)} className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2.5 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 transition"><option value="single">Single</option><option value="ep">EP</option><option value="album">Album</option><option value="mixtape">Mixtape</option></select></div>
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={aiGenerated} onChange={e => setAiGenerated(e.target.checked)} className="sr-only peer" />
            <div className="w-5 h-5 rounded border-2 border-neutral-600 peer-checked:bg-violet-500 peer-checked:border-violet-500 flex items-center justify-center transition">{aiGenerated && <span className="text-white text-xs">✓</span>}</div>
            <span className="text-sm text-neutral-300">AI-generated content</span>
          </label>
        </div>
        <div className="flex gap-3 mt-6">
          <button onClick={onClose} className="flex-1 border border-neutral-700 text-neutral-300 py-2.5 rounded-lg text-sm font-medium hover:bg-neutral-800 transition">Cancel</button>
          <button onClick={() => { if (!title || !date) return; onAdd({ id: 'r' + Date.now(), persona: selectedPersona?.name || '', personaColor: selectedPersona?.color || COLORS[0], title, date, type, aiGenerated, status: 'draft' }); onClose() }} disabled={!title || !date} className="flex-1 bg-violet-500 hover:bg-violet-400 disabled:opacity-40 text-white py-2.5 rounded-lg text-sm font-semibold transition">Create Release</button>
        </div>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [personas, setPersonas] = useState(MOCK_PERSONAS)
  const [releases, setReleases] = useState(MOCK_RELEASES)
  const [showAddPersona, setShowAddPersona] = useState(false)
  const [showAddRelease, setShowAddRelease] = useState(false)
  const [editingPersona, setEditingPersona] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')
  const [checklistRelease, setChecklistRelease] = useState(null)
  const [showCSVUpload, setShowCSVUpload] = useState(false)
  const [csvImported, setCsvImported] = useState(false)
  const [user, setUser] = useState(null)
  const [links, setLinks] = useState(MOCK_LINKS)
  const [editingLinks, setEditingLinks] = useState(null)

  useEffect(() => {
    try {
      const supabase = getSupabase()
      supabase.auth.getUser().then(({ data }) => setUser(data?.user ?? null))
      const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => { setUser(session?.user ?? null) })
      return () => subscription.unsubscribe()
    } catch {}
  }, [])

  const handleSignOut = async () => {
    try { const supabase = getSupabase(); await supabase.auth.signOut(); window.location.href = '/persona-hub' } catch { window.location.href = '/persona-hub' }
  }

  const totalStreams = personas.reduce((s, p) => s + p.streams, 0)
  const totalRevenue = personas.reduce((s, p) => s + p.revenue, 0)
  const activePersonas = personas.filter(p => p.active).length
  const collisionDates = [...new Set(releases.filter((r, _, arr) => arr.some(o => o.date === r.date && o.id !== r.id)).map(r => r.date))]

  const addPersona = ({ name, genre, color }) => { setPersonas(prev => [...prev, { id: String(Date.now()), name, genre, color, releases: 0, streams: 0, revenue: 0, active: true }]) }
  const updatePersona = (id, updates) => { setPersonas(prev => prev.map(p => p.id === id ? { ...p, ...updates } : p)) }
  const togglePersonaActive = (id) => { setPersonas(prev => prev.map(p => p.id === id ? { ...p, active: !p.active } : p)) }
  const addRelease = (release) => { setReleases(prev => [...prev, release]) }
  const handleCSVImport = useCallback((matched) => {
    setPersonas(prev => prev.map(p => { const data = matched[p.id]; if (!data || data.entries.length === 0) return p; return { ...p, revenue: p.revenue + data.totalRevenue, streams: p.streams + data.totalStreams } }))
    setCsvImported(true)
  }, [])

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <nav className="fixed top-0 w-full z-40 border-b border-neutral-800/60 bg-neutral-950/90 backdrop-blur-lg">
        <div className="max-w-6xl mx-auto px-5 h-14 flex items-center justify-between">
          <Link href="/persona-hub" className="text-lg font-bold tracking-tight">Persona<span className="text-violet-400">Hub</span></Link>
          <div className="flex items-center gap-3">
            <button onClick={() => setShowAddPersona(true)} className="text-sm bg-violet-500 hover:bg-violet-400 text-white px-3 py-1.5 rounded-md font-medium transition flex items-center gap-1.5"><span>+</span> New Persona</button>
            {user && <button onClick={handleSignOut} className="text-xs text-neutral-500 hover:text-neutral-300 transition">Sign Out</button>}
          </div>
        </div>
      </nav>

      <div className="pt-14 max-w-6xl mx-auto px-5">
        <div className="flex gap-1 border-b border-neutral-800/60 mt-4 mb-6">
          {['overview', 'releases', 'revenue', 'links', 'analytics', 'settings'].map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)} className={`px-4 py-2.5 text-sm font-medium capitalize transition border-b-2 -mb-px ${activeTab === tab ? 'text-violet-400 border-violet-400' : 'text-neutral-500 border-transparent hover:text-neutral-300'}`}>{tab}</button>
          ))}
        </div>

        {activeTab === 'overview' && (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
              {[{ label: 'Active Personas', value: activePersonas, color: 'text-violet-400' }, { label: 'Total Streams', value: `${(totalStreams / 1000).toFixed(1)}K`, color: 'text-blue-400' }, { label: 'Total Revenue', value: `$${totalRevenue.toFixed(0)}`, color: 'text-emerald-400' }, { label: 'Collisions', value: collisionDates.length > 0 ? `${collisionDates.length} ⚠` : '0', color: collisionDates.length > 0 ? 'text-red-400' : 'text-emerald-400' }].map(stat => (
                <div key={stat.label} className="bg-neutral-900/60 border border-neutral-800/60 rounded-xl p-4"><div className={`text-2xl font-bold tabular-nums ${stat.color}`}>{stat.value}</div><div className="text-[10px] text-neutral-500 uppercase tracking-wider mt-1">{stat.label}</div></div>
              ))}
            </div>
            <div className="mb-8">
              <div className="flex items-center justify-between mb-3"><h2 className="text-sm font-semibold text-neutral-400 uppercase tracking-wider">Your Personas</h2><button onClick={() => setShowAddPersona(true)} className="text-xs text-violet-400 hover:text-violet-300 transition">+ Add</button></div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">{personas.map(p => <PersonaCard key={p.id} persona={p} onEdit={setEditingPersona} />)}</div>
            </div>
            <div className="mb-8">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold text-neutral-400 uppercase tracking-wider">Upcoming Releases</h2>
                <div className="flex items-center gap-2">
                  {collisionDates.length > 0 && <span className="text-xs bg-red-500/15 text-red-400 border border-red-500/30 px-2 py-0.5 rounded font-semibold">{collisionDates.length} date collision{collisionDates.length > 1 ? 's' : ''} detected</span>}
                  <button onClick={() => setShowAddRelease(true)} className="text-xs text-violet-400 hover:text-violet-300 transition">+ Add</button>
                </div>
              </div>
              <div className="bg-neutral-900/40 border border-neutral-800/60 rounded-xl p-4">{releases.sort((a, b) => a.date.localeCompare(b.date)).map(r => <ReleaseRow key={r.id} release={r} allReleases={releases} onClick={() => r.aiGenerated && setChecklistRelease(r)} />)}</div>
              <p className="text-xs text-neutral-600 mt-2">Click any AI release to open the disclosure checklist.</p>
            </div>
          </>
        )}

        {activeTab === 'releases' && (
          <div>
            <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-semibold text-neutral-400 uppercase tracking-wider">Release Calendar</h2><button onClick={() => setShowAddRelease(true)} className="text-xs bg-violet-500 hover:bg-violet-400 text-white px-3 py-1.5 rounded-md font-medium transition">+ New Release</button></div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
              {MONTHS.map(month => {
                const monthReleases = releases.filter(r => { const d = new Date(r.date); return d.toLocaleString('en', { month: 'short', year: 'numeric' }) === month })
                return (
                  <div key={month} className="bg-neutral-900/40 border border-neutral-800/60 rounded-xl p-4">
                    <h3 className="text-sm font-bold mb-3">{month}</h3>
                    {monthReleases.length === 0 ? <p className="text-xs text-neutral-600 py-4 text-center">No releases</p> : (
                      <div className="space-y-2">{monthReleases.map(r => (
                        <div key={r.id} className={`flex items-center gap-2 p-2 bg-neutral-800/40 rounded-lg ${r.aiGenerated ? 'cursor-pointer hover:bg-neutral-800/60' : ''}`} onClick={() => r.aiGenerated && setChecklistRelease(r)}>
                          <div className="w-1 h-6 rounded-full" style={{ background: r.personaColor }} />
                          <div className="flex-1 min-w-0"><div className="text-xs font-medium truncate flex items-center gap-1.5">{r.title}{r.aiGenerated && <span className="text-[9px] bg-violet-500/15 text-violet-400 px-1 rounded">AI</span>}</div><div className="text-[10px] text-neutral-500">{r.persona} · {r.date.split('-').slice(1).join('/')}</div></div>
                        </div>
                      ))}</div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {activeTab === 'revenue' && (
          <div>
            <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-semibold text-neutral-400 uppercase tracking-wider">Revenue by Persona</h2><button onClick={() => setShowCSVUpload(true)} className="text-xs bg-neutral-800 hover:bg-neutral-700 text-neutral-300 px-3 py-1.5 rounded-md font-medium transition">Upload CSV</button></div>
            {csvImported && <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-3 mb-4 flex items-center gap-2"><span className="text-emerald-400">✓</span><span className="text-sm text-emerald-300">CSV imported — revenue updated across matched personas</span></div>}
            <div className="bg-neutral-900/40 border border-neutral-800/60 rounded-xl p-5 mb-6">
              <div className="space-y-3">{personas.filter(p => p.revenue > 0).sort((a, b) => b.revenue - a.revenue).map(p => { const maxRev = Math.max(...personas.map(x => x.revenue)); return (<div key={p.id} className="flex items-center gap-3"><div className="w-20 text-xs font-medium text-right truncate text-neutral-300">{p.name}</div><div className="flex-1 bg-neutral-800/50 rounded-full h-5 overflow-hidden"><div className="h-full rounded-full transition-all duration-500" style={{ width: `${(p.revenue / maxRev) * 100}%`, background: p.color }} /></div><div className="w-16 text-right text-xs font-mono text-emerald-400 tabular-nums">${p.revenue.toFixed(0)}</div></div>) })}</div>
              <div className="flex items-center justify-between mt-4 pt-4 border-t border-neutral-800/60"><span className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Total</span><span className="text-sm font-bold text-emerald-400 tabular-nums">${totalRevenue.toFixed(2)}</span></div>
            </div>
            <div className="bg-neutral-900/40 border border-neutral-800/60 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-neutral-400 uppercase tracking-wider mb-3">How to import</h3>
              <ol className="space-y-2 text-sm text-neutral-400"><li className="flex gap-2"><span className="text-violet-400 font-bold">1.</span> Go to DistroKid → Bank → Stats → Download CSV</li><li className="flex gap-2"><span className="text-violet-400 font-bold">2.</span> Click "Upload CSV" above</li><li className="flex gap-2"><span className="text-violet-400 font-bold">3.</span> We auto-match tracks to your personas by artist name</li><li className="flex gap-2"><span className="text-violet-400 font-bold">4.</span> See revenue broken down per persona, per track, per platform</li></ol>
            </div>
          </div>
        )}

        {activeTab === 'links' && (
          <div>
            <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-semibold text-neutral-400 uppercase tracking-wider">Smart Links by Persona</h2></div>
            <div className="bg-violet-500/8 border border-violet-500/20 rounded-xl p-4 mb-6"><div className="text-sm font-medium text-violet-400 mb-1">One link per persona, all platforms</div><p className="text-xs text-neutral-500">Share a single link that routes fans to their preferred streaming platform. Edit links below to configure each persona's streaming profiles.</p></div>
            <div className="space-y-4">
              {personas.map(p => {
                const personaLinks = links[p.id] || {}
                const connectedCount = PLATFORMS.filter(pl => personaLinks[pl.id]).length
                const isEditing = editingLinks === p.id
                return (
                  <div key={p.id} className="bg-neutral-900/40 border border-neutral-800/60 rounded-xl overflow-hidden">
                    <div className="flex items-center gap-3 p-4 cursor-pointer hover:bg-neutral-800/30 transition" onClick={() => setEditingLinks(isEditing ? null : p.id)}>
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold flex-shrink-0" style={{ background: p.color }}>{p.name[0]}</div>
                      <div className="flex-1 min-w-0"><div className="font-semibold text-sm">{p.name}</div><div className="text-xs text-neutral-500">{p.genre}</div></div>
                      <div className="flex items-center gap-2">
                        <div className="flex -space-x-1">{PLATFORMS.filter(pl => personaLinks[pl.id]).map(pl => (<div key={pl.id} className="w-5 h-5 rounded-full border-2 border-neutral-900 flex items-center justify-center" style={{ background: pl.color }}><span className="text-[8px] text-white font-bold">{pl.name[0]}</span></div>))}</div>
                        <span className="text-xs text-neutral-500 tabular-nums">{connectedCount}/{PLATFORMS.length}</span>
                        <span className="text-neutral-600 text-sm">{isEditing ? '−' : '+'}</span>
                      </div>
                    </div>
                    {isEditing && (
                      <div className="border-t border-neutral-800/60 p-4 space-y-3">
                        <div className="bg-neutral-800/30 rounded-lg p-3 mb-3"><div className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1">Smart Link URL</div><div className="text-sm text-violet-400 font-mono">personahub.app/{p.name.toLowerCase().replace(/[^a-z0-9]/g, '-')}</div></div>
                        {PLATFORMS.map(pl => (
                          <div key={pl.id} className="flex items-center gap-3">
                            <div className="w-6 h-6 rounded flex items-center justify-center flex-shrink-0" style={{ background: pl.color + '20' }}><span className="text-[10px] font-bold" style={{ color: pl.color }}>{pl.name[0]}</span></div>
                            <span className="text-xs font-medium text-neutral-400 w-24 flex-shrink-0">{pl.name}</span>
                            <input type="text" value={personaLinks[pl.id] || ''} onChange={e => setLinks(prev => ({ ...prev, [p.id]: { ...prev[p.id], [pl.id]: e.target.value } }))} placeholder={pl.prefix} className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-xs text-neutral-100 placeholder:text-neutral-700 focus:outline-none focus:border-violet-500 transition font-mono" />
                            {personaLinks[pl.id] && <span className="text-emerald-400 text-xs flex-shrink-0">Connected</span>}
                          </div>
                        ))}
                        <div className="flex gap-2 pt-2">
                          <button className="text-xs bg-violet-500 hover:bg-violet-400 text-white px-4 py-2 rounded-lg font-medium transition">Save Links</button>
                          <Link href={`/persona-hub/link/${p.name.toLowerCase().replace(/[^a-z0-9]/g, '-')}`} target="_blank" className="text-xs bg-neutral-800 hover:bg-neutral-700 text-neutral-300 px-4 py-2 rounded-lg font-medium transition">Preview Smart Link Page</Link>
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
            <div className="bg-neutral-900/40 border border-neutral-800/60 rounded-xl p-5 mt-6">
              <h3 className="text-sm font-semibold text-neutral-400 uppercase tracking-wider mb-3">How Smart Links work</h3>
              <ol className="space-y-2 text-sm text-neutral-400"><li className="flex gap-2"><span className="text-violet-400 font-bold">1.</span> Add your streaming profiles for each persona above</li><li className="flex gap-2"><span className="text-violet-400 font-bold">2.</span> Share one link per persona — fans pick their platform</li><li className="flex gap-2"><span className="text-violet-400 font-bold">3.</span> Use as pre-save links before release day</li><li className="flex gap-2"><span className="text-violet-400 font-bold">4.</span> Track clicks per platform in Cross-Persona Analytics</li></ol>
            </div>
          </div>
        )}

        {activeTab === 'analytics' && (
          <div>
            <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-semibold text-neutral-400 uppercase tracking-wider">Cross-Persona Analytics</h2><span className="text-xs text-neutral-600">Last 6 months</span></div>
            <div className="bg-neutral-900/40 border border-neutral-800/60 rounded-xl p-5 mb-6">
              <div className="flex items-center justify-between mb-4"><h3 className="text-sm font-semibold text-neutral-400 uppercase tracking-wider">Monthly Growth</h3><div className="flex items-center gap-4 text-xs text-neutral-500"><span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-violet-500 inline-block" /> Streams</span><span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded bg-emerald-500 inline-block" /> Revenue</span></div></div>
              <div className="flex items-end gap-3 h-40">{MOCK_MONTHLY_GROWTH.map((m) => { const maxStreams = Math.max(...MOCK_MONTHLY_GROWTH.map(x => x.streams)); const barH = Math.max((m.streams / maxStreams) * 100, 4); return (<div key={m.month} className="flex-1 flex flex-col items-center gap-1"><div className="w-full flex flex-col items-center justify-end flex-1"><div className="text-[10px] text-emerald-400 tabular-nums mb-0.5">${m.revenue.toFixed(0)}</div><div className="text-[10px] text-neutral-500 tabular-nums mb-1">{(m.streams / 1000).toFixed(1)}K</div><div className="w-full rounded-t-md bg-violet-500/50 transition-all relative" style={{ height: `${barH}%` }}><div className="absolute bottom-0 left-0 right-0 rounded-t-md bg-emerald-500/40" style={{ height: `${Math.max((m.revenue / maxStreams * 1000) * 100, 4)}%` }} /></div></div><div className="text-[10px] text-neutral-600 font-medium">{m.month}</div></div>) })}</div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <div className="bg-neutral-900/40 border border-neutral-800/60 rounded-xl p-5"><h3 className="text-sm font-semibold text-neutral-400 uppercase tracking-wider mb-4">By Platform</h3><div className="space-y-2.5">{MOCK_PLATFORM_STREAMS.map(p => (<div key={p.platform} className="flex items-center gap-3"><div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: p.color }} /><span className="text-xs font-medium text-neutral-300 w-24">{p.platform}</span><div className="flex-1 bg-neutral-800/50 rounded-full h-3 overflow-hidden"><div className="h-full rounded-full transition-all" style={{ width: `${p.pct}%`, background: p.color + 'aa' }} /></div><span className="text-[10px] text-neutral-500 tabular-nums w-10 text-right">{p.pct}%</span><span className="text-[10px] text-neutral-600 tabular-nums w-14 text-right">{(p.streams / 1000).toFixed(1)}K</span></div>))}</div></div>
              <div className="bg-neutral-900/40 border border-neutral-800/60 rounded-xl p-5"><h3 className="text-sm font-semibold text-neutral-400 uppercase tracking-wider mb-4">By Country</h3><div className="space-y-2.5">{MOCK_GEO.map(g => (<div key={g.country} className="flex items-center gap-3"><span className="text-xs font-medium text-neutral-300 w-28 truncate">{g.country}</span><div className="flex-1 bg-neutral-800/50 rounded-full h-3 overflow-hidden"><div className="h-full rounded-full bg-violet-500/50 transition-all" style={{ width: `${g.pct}%` }} /></div><span className="text-[10px] text-neutral-500 tabular-nums w-10 text-right">{g.pct}%</span><span className="text-[10px] text-neutral-600 tabular-nums w-14 text-right">{(g.streams / 1000).toFixed(1)}K</span></div>))}</div></div>
            </div>
            <div className="bg-neutral-900/40 border border-neutral-800/60 rounded-xl p-5 mb-6"><h3 className="text-sm font-semibold text-neutral-400 uppercase tracking-wider mb-4">Top Tracks (All Personas)</h3><div className="space-y-0">{MOCK_TOP_TRACKS.map((t, i) => (<div key={t.title} className="flex items-center gap-3 py-2.5 border-b border-neutral-800/40 last:border-b-0"><span className="text-xs text-neutral-600 w-5 text-right tabular-nums font-medium">{i + 1}</span><div className="w-1 h-6 rounded-full" style={{ background: t.personaColor }} /><div className="flex-1 min-w-0"><div className="text-sm font-medium truncate">{t.title}</div><div className="text-xs text-neutral-500">{t.persona}</div></div><div className="text-right flex-shrink-0"><div className="text-xs tabular-nums text-neutral-300">{(t.streams / 1000).toFixed(1)}K streams</div><div className="text-[10px] tabular-nums text-emerald-400">${t.revenue.toFixed(2)}</div></div></div>))}</div></div>
            <div className="bg-neutral-900/40 border border-neutral-800/60 rounded-xl p-5"><h3 className="text-sm font-semibold text-neutral-400 uppercase tracking-wider mb-4">Persona Performance</h3><div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">{personas.filter(p => p.active).sort((a, b) => b.streams - a.streams).map(p => { const maxStreams = Math.max(...personas.filter(x => x.active).map(x => x.streams)); return (<div key={p.id} className="bg-neutral-800/30 rounded-lg p-3"><div className="flex items-center gap-2 mb-2"><div className="w-6 h-6 rounded flex items-center justify-center text-white text-[10px] font-bold" style={{ background: p.color }}>{p.name[0]}</div><span className="text-sm font-semibold truncate">{p.name}</span></div><div className="bg-neutral-700/30 rounded-full h-1.5 mb-2"><div className="h-full rounded-full" style={{ width: `${(p.streams / maxStreams) * 100}%`, background: p.color }} /></div><div className="flex justify-between text-xs"><span className="text-neutral-500 tabular-nums">{(p.streams / 1000).toFixed(1)}K streams</span><span className="text-emerald-400 tabular-nums">${p.revenue.toFixed(0)}</span></div></div>) })}</div></div>
          </div>
        )}

        {activeTab === 'settings' && (
          <div>
            <h2 className="text-sm font-semibold text-neutral-400 uppercase tracking-wider mb-4">Account Settings</h2>
            <div className="space-y-4">
              <div className="bg-neutral-900/40 border border-neutral-800/60 rounded-xl p-5">
                <h3 className="text-sm font-semibold mb-4">Profile</h3>
                <div className="space-y-3">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-full bg-violet-500/20 border border-violet-500/30 flex items-center justify-center text-violet-400 text-lg font-bold">
                      {user?.email?.[0]?.toUpperCase() || 'U'}
                    </div>
                    <div>
                      <div className="text-sm font-medium">{user?.email || 'demo@personahub.app'}</div>
                      <div className="text-xs text-neutral-500">Signed in via {user?.app_metadata?.provider === 'google' ? 'Google' : 'Email'}</div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-neutral-900/40 border border-neutral-800/60 rounded-xl p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold">Your Plan</h3>
                  <span className="text-xs bg-violet-500/15 text-violet-400 border border-violet-500/30 px-2 py-0.5 rounded font-semibold uppercase tracking-wider">Free</span>
                </div>
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <div className="text-2xl font-bold tabular-nums">{personas.length}<span className="text-sm font-normal text-neutral-500">/3</span></div>
                    <div className="text-[10px] text-neutral-500 uppercase tracking-wider mt-1">Personas Used</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold tabular-nums text-emerald-400">$0<span className="text-sm font-normal text-neutral-500">/mo</span></div>
                    <div className="text-[10px] text-neutral-500 uppercase tracking-wider mt-1">Current Cost</div>
                  </div>
                </div>
                <div className="bg-neutral-800/50 rounded-lg p-3 mb-4">
                  <div className="text-xs font-semibold text-neutral-400 mb-2">Free plan includes:</div>
                  <ul className="space-y-1">
                    {['3 personas', 'Release calendar', 'AI disclosure checklist', 'Basic revenue view'].map(f => (
                      <li key={f} className="flex gap-2 text-xs text-neutral-500"><span className="text-violet-400">✓</span>{f}</li>
                    ))}
                  </ul>
                </div>
                <button className="w-full bg-violet-500 hover:bg-violet-400 text-white py-2.5 rounded-lg text-sm font-semibold transition">
                  Upgrade to Pro — $9/mo
                </button>
                <p className="text-[10px] text-neutral-600 text-center mt-2">Unlimited personas, CSV revenue import, analytics export, priority support</p>
              </div>

              <div className="bg-neutral-900/40 border border-neutral-800/60 rounded-xl p-5">
                <h3 className="text-sm font-semibold mb-4">Data & Export</h3>
                <div className="space-y-2">
                  <button className="w-full flex items-center gap-3 p-3 bg-neutral-800/40 hover:bg-neutral-800/60 rounded-lg transition text-left">
                    <span className="text-base">📊</span>
                    <div><div className="text-sm font-medium">Export Analytics</div><div className="text-xs text-neutral-500">Download streams, revenue, and growth data as CSV</div></div>
                  </button>
                  <button className="w-full flex items-center gap-3 p-3 bg-neutral-800/40 hover:bg-neutral-800/60 rounded-lg transition text-left">
                    <span className="text-base">📋</span>
                    <div><div className="text-sm font-medium">Export AI Audit Log</div><div className="text-xs text-neutral-500">Download all AI disclosure records for compliance</div></div>
                  </button>
                  <button className="w-full flex items-center gap-3 p-3 bg-neutral-800/40 hover:bg-neutral-800/60 rounded-lg transition text-left">
                    <span className="text-base">📦</span>
                    <div><div className="text-sm font-medium">Export All Data</div><div className="text-xs text-neutral-500">Full account backup — personas, releases, links, revenue</div></div>
                  </button>
                </div>
              </div>

              <div className="bg-neutral-900/40 border border-red-500/20 rounded-xl p-5">
                <h3 className="text-sm font-semibold text-red-400 mb-4">Danger Zone</h3>
                <div className="space-y-2">
                  <div className="flex items-center justify-between p-3 bg-neutral-800/40 rounded-lg">
                    <div><div className="text-sm font-medium">Delete all personas</div><div className="text-xs text-neutral-500">Remove all personas and their data</div></div>
                    <button className="text-xs border border-red-500/30 text-red-400 hover:bg-red-500/10 px-3 py-1.5 rounded-lg font-medium transition">Delete All</button>
                  </div>
                  <div className="flex items-center justify-between p-3 bg-neutral-800/40 rounded-lg">
                    <div><div className="text-sm font-medium">Delete account</div><div className="text-xs text-neutral-500">Permanently delete your account and all data</div></div>
                    <button className="text-xs border border-red-500/30 text-red-400 hover:bg-red-500/10 px-3 py-1.5 rounded-lg font-medium transition">Delete Account</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="h-12" />
      </div>

      {showAddPersona && <AddPersonaModal onClose={() => setShowAddPersona(false)} onAdd={addPersona} />}
      {editingPersona && <EditPersonaModal persona={editingPersona} onClose={() => setEditingPersona(null)} onSave={updatePersona} onToggleActive={togglePersonaActive} />}
      {checklistRelease && <AIChecklistModal release={checklistRelease} onClose={() => setChecklistRelease(null)} />}
      {showCSVUpload && <CSVUploadModal onClose={() => setShowCSVUpload(false)} personas={personas} onImport={handleCSVImport} />}
      {showAddRelease && <AddReleaseModal onClose={() => setShowAddRelease(false)} onAdd={addRelease} personas={personas} />}
    </div>
  )
}
