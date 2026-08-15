export default function robots() {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: [],
      },
    ],
    sitemap: "https://imprint-yoojinesong-3887s-projects.vercel.app/sitemap.xml",
  };
}
