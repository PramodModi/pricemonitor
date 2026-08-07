/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ['class'],
  content: [
    './src/app/**/*.{js,jsx}',
    './src/components/**/*.{js,jsx}',
    './src/pages/**/*.{js,jsx}',
  ],
  theme: {
    container: {
      center: true,
      padding: '1rem',
      screens: {
        sm: '640px',
        md: '768px',
        lg: '1024px',
        xl: '1280px',
      },
    },
    extend: {
      colors: {
        // Primary — deep indigo (trust, intelligence)
        primary: {
          50:  '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          300: '#a5b4fc',
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
          800: '#3730a3',
          900: '#312e81',
          950: '#1e1b4b',
          DEFAULT: '#4f46e5',
        },
        // Accent — warm amber (price urgency, deals, CTAs)
        accent: {
          50:  '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          300: '#fcd34d',
          400: '#fbbf24',
          500: '#f59e0b',
          600: '#d97706',
          700: '#b45309',
          800: '#92400e',
          900: '#78350f',
          DEFAULT: '#f59e0b',
        },
        // Success — for "in stock", "price drop", "tracked"
        success: {
          50:  '#f0fdf4',
          500: '#22c55e',
          600: '#16a34a',
          DEFAULT: '#16a34a',
        },
        // Danger — out of stock, high price, remove
        danger: {
          50:  '#fef2f2',
          500: '#ef4444',
          600: '#dc2626',
          DEFAULT: '#dc2626',
        },
        // Neutral surface
        surface: '#f8fafc',
        border: '#e2e8f0',
      },
      fontFamily: {
        display: ['Sora', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      fontSize: {
        'display-xl': ['3.5rem', { lineHeight: '1.1', letterSpacing: '-0.03em', fontWeight: '700' }],
        'display-lg': ['2.5rem', { lineHeight: '1.15', letterSpacing: '-0.025em', fontWeight: '700' }],
        'display-md': ['2rem',   { lineHeight: '1.2',  letterSpacing: '-0.02em',  fontWeight: '600' }],
        'display-sm': ['1.5rem', { lineHeight: '1.3',  letterSpacing: '-0.015em', fontWeight: '600' }],
      },
      boxShadow: {
        'card':   '0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.04)',
        'card-md':'0 4px 12px 0 rgb(0 0 0 / 0.08), 0 2px 4px -2px rgb(0 0 0 / 0.04)',
        'card-lg':'0 10px 40px 0 rgb(0 0 0 / 0.10), 0 4px 6px -4px rgb(0 0 0 / 0.04)',
        'input-focus': '0 0 0 3px rgb(99 102 241 / 0.18)',
        'amber-glow':  '0 0 0 3px rgb(245 158 11 / 0.25)',
      },
      borderRadius: {
        DEFAULT: '0.5rem',
        lg: '0.75rem',
        xl: '1rem',
        '2xl': '1.25rem',
      },
      keyframes: {
        'pulse-border': {
          '0%, 100%': { boxShadow: '0 0 0 0 rgb(99 102 241 / 0)' },
          '50%':       { boxShadow: '0 0 0 4px rgb(99 102 241 / 0.20)' },
        },
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-up': {
          from: { opacity: '0', transform: 'translateY(16px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        'skeleton-shimmer': {
          '0%':   { backgroundPosition: '-400px 0' },
          '100%': { backgroundPosition: '400px 0' },
        },
      },
      animation: {
        'pulse-border':     'pulse-border 2s ease-in-out infinite',
        'fade-in':          'fade-in 0.25s ease-out',
        'slide-up':         'slide-up 0.35s ease-out',
        'skeleton-shimmer': 'skeleton-shimmer 1.4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
