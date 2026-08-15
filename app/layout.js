import "./globals.css";

export const metadata = {
  title: "imprint — find your purpose, make your mark",
  description:
    "Discover what gives you purpose through evidence-based questions, then find real opportunities to make a difference in the place you love. Earn impact points. Redeem for experiences.",
  metadataBase: new URL("https://imprint-yoojinesong-3887s-projects.vercel.app"),
  openGraph: {
    title: "imprint — find your purpose, make your mark",
    description:
      "Discover your purpose archetype, find volunteer opportunities near you, and make tax-deductible donations to causes you care about.",
    url: "/",
    siteName: "imprint",
    images: [{ url: "/icons/icon-512.png", width: 512, height: 512, alt: "imprint app icon" }],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "imprint — find your purpose, make your mark",
    description:
      "Discover your purpose archetype, find volunteer opportunities, and make a real difference.",
    images: ["/icons/icon-512.png"],
  },
  robots: { index: true, follow: true },
  alternates: { canonical: "/" },
  manifest: "/manifest.json",
  icons: {
    icon: "/favicon.png",
    apple: "/icons/icon-180.png",
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "imprint",
  },
  other: {
    "mobile-web-app-capable": "yes",
    "apple-mobile-web-app-capable": "yes",
  },
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#2a6f5e" },
    { media: "(prefers-color-scheme: dark)", color: "#0f1923" },
  ],
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="apple-touch-icon" sizes="180x180" href="/icons/icon-180.png" />
        <link rel="apple-touch-icon" sizes="152x152" href="/icons/icon-152.png" />
        <link rel="apple-touch-icon" sizes="144x144" href="/icons/icon-144.png" />
        <link
          rel="apple-touch-startup-image"
          media="(device-width: 375px) and (device-height: 812px) and (-webkit-device-pixel-ratio: 3)"
          href="/icons/splash-1125x2436.png"
        />
        <link
          rel="apple-touch-startup-image"
          media="(device-width: 414px) and (device-height: 896px) and (-webkit-device-pixel-ratio: 3)"
          href="/icons/splash-1242x2688.png"
        />
        <link
          rel="apple-touch-startup-image"
          media="(device-width: 414px) and (device-height: 896px) and (-webkit-device-pixel-ratio: 2)"
          href="/icons/splash-828x1792.png"
        />
        <link
          rel="apple-touch-startup-image"
          media="(device-width: 390px) and (device-height: 844px) and (-webkit-device-pixel-ratio: 3)"
          href="/icons/splash-1170x2532.png"
        />
        <link
          rel="apple-touch-startup-image"
          media="(device-width: 428px) and (device-height: 926px) and (-webkit-device-pixel-ratio: 3)"
          href="/icons/splash-1284x2778.png"
        />
        <link
          rel="apple-touch-startup-image"
          media="(device-width: 430px) and (device-height: 932px) and (-webkit-device-pixel-ratio: 3)"
          href="/icons/splash-1290x2796.png"
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "WebApplication",
              name: "imprint",
              description:
                "Discover what gives you purpose, then find real opportunities to make a difference in the place you love.",
              url: "https://imprint-yoojinesong-3887s-projects.vercel.app",
              applicationCategory: "LifestyleApplication",
              operatingSystem: "Any",
              offers: {
                "@type": "Offer",
                price: "0",
                priceCurrency: "USD",
              },
              author: {
                "@type": "Organization",
                name: "imprint",
              },
            }),
          }}
        />
      </head>
      <body>
        <a href="#main-content" className="skip-nav">Skip to content</a>
        <noscript>
          <div style={{ padding: "60px 24px", textAlign: "center", fontFamily: "system-ui, sans-serif", color: "#1c1917" }}>
            <div style={{ fontSize: "48px", marginBottom: "16px" }}>🍀</div>
            <h1 style={{ fontSize: "24px", fontWeight: 700, marginBottom: "8px" }}>imprint</h1>
            <p style={{ fontSize: "15px", color: "#57534e", maxWidth: "360px", margin: "0 auto", lineHeight: 1.6 }}>
              This app requires JavaScript to run. Please enable JavaScript in your browser settings to discover your purpose and make your mark.
            </p>
          </div>
        </noscript>
        {children}
      </body>
    </html>
  );
}
