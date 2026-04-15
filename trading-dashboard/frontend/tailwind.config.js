/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#0f1117',
          card:    '#161b27',
          hover:   '#1e2535',
          border:  '#252d3d',
        },
        accent: {
          blue:   '#3b82f6',
          green:  '#22c55e',
          red:    '#ef4444',
          yellow: '#eab308',
          orange: '#f97316',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
}
