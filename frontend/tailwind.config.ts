import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{vue,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: "#07C160",
        canvas: "#F7F7F7",
        surface: "#FFFFFF",
        ink: "#191919",
        muted: "#999999",
        glow: "#E1F8EA",
      },
      fontFamily: {
        display: ["Space Grotesk", "Noto Sans SC", "sans-serif"],
        body: ["Noto Sans SC", "Space Grotesk", "sans-serif"],
      },
      boxShadow: {
        panel: "0 20px 48px rgba(25, 25, 25, 0.07), 0 4px 14px rgba(7, 193, 96, 0.05)",
      },
      backgroundImage: {
        mesh: "radial-gradient(circle at top left, rgba(7,193,96,0.14), transparent 28%), radial-gradient(circle at 90% 0%, rgba(225,248,234,0.9), transparent 22%), radial-gradient(circle at 50% 100%, rgba(7,193,96,0.08), transparent 30%)",
      },
    },
  },
  plugins: [],
} satisfies Config;
