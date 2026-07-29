import type { Metadata } from "next";
import AuthGuard from "@/components/AuthGuard";
import ThemeProvider from "@/components/ThemeProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "LedgerFlow",
  description: "Personal finance tracker with AI-powered categorisation",
};

// Applies the saved theme before React hydrates, so there's no flash of
// the wrong theme on load. Kept tiny and inline (not a separate script
// file) so it runs synchronously as the very first thing in <body>.
const THEME_BOOTSTRAP = `
(function () {
  try {
    var t = localStorage.getItem("ledgerflow-theme");
    if (t === "light" || t === "dark") {
      document.documentElement.setAttribute("data-theme", t);
    }
  } catch (e) {}
})();
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }} />
        <ThemeProvider>
          <AuthGuard>{children}</AuthGuard>
        </ThemeProvider>
      </body>
    </html>
  );
}
