import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        upds: {
          navy: '#003366',
          blue: '#0066CC',
          sky: '#4DA8DA',
          white: '#FFFFFF',
          'navy-light': '#004080',
          'blue-light': '#3388DD',
          'sky-light': '#7CC0E8',
        },
      },
    },
  },
}

export default config
