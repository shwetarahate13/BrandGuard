/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#fbf8f3",
          100: "#f5eee2",
          200: "#eadbc4",
          300: "#dcc39e",
          400: "#cb9f67",
          500: "#bf8741",
          600: "#aa6e35",
          700: "#89522d",
          800: "#70432a",
          900: "#5d3826",
          950: "#341d13",
        },
      },
    },
  },
  plugins: [],
}
