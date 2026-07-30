import './globals.css'

export const metadata = {
  title: 'DetailBook — Solo Detailer Booking',
  description: 'The booking & payment app built for solo mobile auto detailers. $39/mo, no hidden fees.',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="bg-neutral-950 text-neutral-100 antialiased">
        {children}
      </body>
    </html>
  )
}
