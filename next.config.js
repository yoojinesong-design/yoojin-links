/** @type {import('next').NextConfig} */
const nextConfig = {
  // For Capacitor mobile builds, static export is enabled via MOBILE_BUILD=1
  // Run: npm run build:mobile
  ...(process.env.MOBILE_BUILD === "1" && {
    output: "export",
    trailingSlash: true,
  }),
};

export default nextConfig;
