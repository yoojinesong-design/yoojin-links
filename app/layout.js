export const metadata = {
  title: 'Yoojin Links',
  description: 'B2B Micro-SaaS Reports',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body style={{ margin: 0 }}>{children}</body>
    </html>
  )
}
