/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        "brand-green": "#006241",
        "brand-accent": "#00754A",
        "brand-house": "#1E3932",
        "brand-light": "#D4E9E2",
        "surface-page": "var(--surface-page)",
        "surface-card": "var(--surface-card)",
        "surface-subtle": "var(--surface-subtle)",
        "text-primary": "var(--text-primary)",
        "text-body": "var(--text-body)",
        "text-muted": "var(--text-muted)",
        "border-subtle": "var(--border-subtle)",
        "border-control": "var(--border-control)",
        "status-success": "var(--status-success-text)",
        "status-warning": "var(--status-warning-text)",
        "status-danger": "var(--status-danger-text)",
        brand: {
          50: "rgb(var(--brand-50) / <alpha-value>)",
          100: "rgb(var(--brand-100) / <alpha-value>)",
          200: "rgb(var(--brand-200) / <alpha-value>)",
          300: "rgb(var(--brand-300) / <alpha-value>)",
          400: "rgb(var(--brand-400) / <alpha-value>)",
          500: "rgb(var(--brand-500) / <alpha-value>)",
          600: "rgb(var(--brand-600) / <alpha-value>)",
          700: "rgb(var(--brand-700) / <alpha-value>)",
          800: "rgb(var(--brand-800) / <alpha-value>)",
          900: "rgb(var(--brand-900) / <alpha-value>)",
          950: "rgb(var(--brand-950) / <alpha-value>)",
        },
        page: "var(--surface-page)",
        surface: "var(--surface-card)",
        "surface-muted": "var(--surface-subtle)",
        "text-primary": "var(--text-primary)",
        "text-secondary": "var(--text-secondary)",
        "border-default": "var(--border-subtle)",
      },
      fontFamily: {
        sans: ["Helvetica Neue", "Helvetica", "Arial", "sans-serif"],
      },
      borderRadius: {
        card: "var(--radius-card)",
        pill: "var(--radius-pill)",
      },
      boxShadow: {
        card: "var(--shadow-card)",
        floating: "var(--shadow-floating)",
      },
    },
  },
  plugins: [],
}
