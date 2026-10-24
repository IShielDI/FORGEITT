// One address for everything: the browser talks to this site, and /api/* is passed on to the backend.
// That lets teammates open a single link (for example a Cloudflare tunnel to port 3000).
const backend = process.env.BACKEND_URL || "http://127.0.0.1:8000";
module.exports = {
  reactStrictMode: true,
  compress: false,               // gzip would hold back the live activity stream
  async rewrites() { return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }]; },
};
