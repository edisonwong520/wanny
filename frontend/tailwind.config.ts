import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{vue,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: "#07C160",
        brandLight: "#9CDA62",
        ink: "#333333",
        muted: "#888888",
        canvas: "#FFFFFF",
        surface: "#F7F7F7",
        secondary: "#EDEDED",
      },
      fontFamily: {
        sans: ["Noto Sans SC", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;