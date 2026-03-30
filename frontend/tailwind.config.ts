import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{vue,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: "#07C160",
        canvas: "#FAF6E8",
        surface: "#FFFFFF",
        ink: "#191919",
        muted: "#999999",
        glow: "#E1F8EA",
      },
      fontFamily: {
        display: ["Space Grotesk", "Noto Sans SC", "sans-serif"],
        body: ["Noto Sans SC", "Space Grotesk", "sans-serif"],
      },
      backgroundImage: {
        mesh: "radial-gradient(circle at top left, rgba(244,218,158,0.34), transparent 28%), radial-gradient(circle at 90% 0%, rgba(255,244,210,0.92), transparent 22%), radial-gradient(circle at 50% 100%, rgba(232,204,148,0.18), transparent 30%)",
      },
    },
  },
  plugins: [],
} satisfies Config;
