import "./globals.css";
export const metadata = { title: "ForgeIt", description: "Forged by agents. Checked by a referee." };
export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <header className="top">
          <a href="/" className="brand">ForgeIt</a>
          <span className="tagline">Forged by agents. Checked by a referee.</span>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
