/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background:    "#091423",
        surface:       "#162030",
        "surface-low": "#121c2b",
        primary:       "#a5e7ff",
        accent:        "#00d2ff",
        text:          "#d9e3f8",
        muted:         "#bbc9cf",
      },
      fontFamily: {
        manrope: ["Manrope", "sans-serif"],
        inter:   ["Inter",   "sans-serif"],
      },
    },
  },
  plugins: [],
};
