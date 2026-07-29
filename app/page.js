const reports = [
  {
    title: 'Dental Insurance Verification — Competitive Strategy',
    path: '/reports/dental-verification-competitive-analysis.html',
    tag: 'Strategy',
  },
  {
    title: 'B2B Micro-SaaS: Job Posting Reverse Research',
    path: '/reports/b2b-job-reverse-research.html',
    tag: 'Research',
  },
  {
    title: 'DetailBook — Landing Page',
    path: '/reports/landing-detailbook.html',
    tag: 'Landing',
  },
  {
    title: 'MenuPulse — Landing Page',
    path: '/reports/landing-menupulse.html',
    tag: 'Landing',
  },
  {
    title: 'DetailBook — Product Spec',
    path: '/reports/spec-detailbook.html',
    tag: 'Spec',
  },
  {
    title: 'MenuPulse — Product Spec',
    path: '/reports/spec-menupulse.html',
    tag: 'Spec',
  },
  {
    title: 'B2B Micro-SaaS Opportunities',
    path: '/reports/b2b-microsaas-opportunities.html',
    tag: 'Research',
  },
]

export default function Home() {
  return (
    <div style={{
      minHeight: '100vh',
      background: '#0C1B2E',
      color: '#D4CFC5',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
      padding: '64px 24px',
    }}>
      <div style={{ maxWidth: 720, margin: '0 auto' }}>
        <h1 style={{
          fontSize: 32,
          fontWeight: 700,
          color: '#E8E4DC',
          marginBottom: 8,
          letterSpacing: -0.5,
        }}>
          Yoojin Links
        </h1>
        <p style={{
          fontSize: 15,
          color: '#6E7B88',
          marginBottom: 48,
        }}>
          B2B Micro-SaaS Research &amp; Reports
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {reports.map((r) => (
            <a
              key={r.path}
              href={r.path}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 16,
                background: '#122240',
                border: '1px solid #1A3050',
                borderRadius: 8,
                padding: '16px 20px',
                textDecoration: 'none',
                color: '#D4CFC5',
              }}
            >
              <span style={{ fontSize: 15, fontWeight: 600 }}>{r.title}</span>
              <span style={{
                fontSize: 11,
                fontWeight: 600,
                background: '#1A3050',
                color: '#6E9AD4',
                padding: '3px 8px',
                borderRadius: 3,
                letterSpacing: 0.5,
                textTransform: 'uppercase',
                flexShrink: 0,
              }}>
                {r.tag}
              </span>
            </a>
          ))}
        </div>
      </div>
    </div>
  )
}
