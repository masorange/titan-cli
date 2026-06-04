import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        titan: {
          background: '#f3edf6',
          panel: '#ffffff',
          ink: '#221b26',
          accent: '#124076',
          soft: '#f0f7ff',
          border: '#e6ddec',
        },
      },
      boxShadow: {
        titan: '0 8px 24px rgba(26, 26, 26, 0.12)',
      },
    },
  },
  plugins: [],
} satisfies Config
