import "@fontsource-variable/archivo/wdth.css";
import "@fontsource/jetbrains-mono/400.css";
import "./globals.css";
export const metadata = { title: "ForgeIt", description: "ForgeIt: forged by agents, checked by a referee." };
export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <header className="top">
          <a href="/" className="brand" aria-label="ForgeIt home">
            <svg viewBox="0 0 26 26" aria-hidden="true"><rect width="26" height="26" rx="7" fill="currentColor" /><path d="M6 17h14l-2.2 4H8.2z" fill="var(--paper)" /><path d="M8 13h10v3H8z" fill="var(--paper)" opacity=".55" /><path d="M16.5 4.5l1.2 2.6 2.6 1.2-2.6 1.2-1.2 2.6-1.2-2.6-2.6-1.2 2.6-1.2z" fill="var(--heat)" /></svg>
            ForgeIt
          </a>
          <span className="heat" aria-hidden="true" />
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
