/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        fintrust: {
          // Brand Blue
          primary: {
            DEFAULT: '#1A73E8',
            hover: '#1765CC',
            light: '#E8F0FE',
            dark: '#8AB4F8',
            'dark-hover': '#AECBFA',
          },
          navy: {
            DEFAULT: '#233044',
            light: '#2C3E55',
            dark: '#1A2332',
          },
          slate: {
            DEFAULT: '#5F6368',
            light: '#80868B',
            dark: '#BDC1C6',
          },
          // Light Surfaces
          light: {
            bg: '#F7F9FC',
            surface: '#FFFFFF',
            subtle: '#F1F3F4',
            border: '#DADCE0',
            text: '#202124',
            muted: '#5F6368',
          },
          // Dark Surfaces
          dark: {
            bg: '#171B24',
            surface: '#202632',
            elevated: '#252D3A',
            border: '#394150',
            text: '#E8EAED',
            muted: '#BDC1C6',
          },
          // Semantic statuses
          success: {
            DEFAULT: '#188038',
            light: '#E6F4EA',
            dark: '#81C995',
          },
          warning: {
            DEFAULT: '#F9AB00',
            light: '#FEF7E0',
            dark: '#FDD663',
          },
          danger: {
            DEFAULT: '#D93025',
            light: '#FCE8E6',
            dark: '#F28B82',
          },
          info: {
            DEFAULT: '#1A73E8',
            light: '#E8F0FE',
            dark: '#8AB4F8',
          },
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'Courier New', 'monospace'],
      },
      borderRadius: {
        sm: '6px',
        md: '10px',
        lg: '14px',
        xl: '18px',
      },
      boxShadow: {
        sm: '0 1px 2px 0 rgba(60, 64, 67, 0.3), 0 1px 3px 1px rgba(60, 64, 67, 0.15)',
        md: '0 1px 3px 0 rgba(60, 64, 67, 0.3), 0 4px 8px 3px rgba(60, 64, 67, 0.15)',
        lg: '0 2px 6px 2px rgba(60, 64, 67, 0.15), 0 8px 12px 4px rgba(60, 64, 67, 0.15)',
        elevated: '0 4px 16px rgba(0, 0, 0, 0.12)',
        'dark-sm': '0 1px 3px 0 rgba(0, 0, 0, 0.4)',
        'dark-md': '0 4px 12px 0 rgba(0, 0, 0, 0.5)',
      },
    },
  },
  plugins: [],
}
