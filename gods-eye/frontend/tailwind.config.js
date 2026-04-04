/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          0: '#0A0A0F',
          1: '#0F1117',
          2: '#161922',
          3: '#1C1F2B',
          4: '#242836',
        },
        primary: {
          glow: '#00F0FF',
          DEFAULT: '#00D4E0',
          muted: '#00A8B3',
          dim: '#007A82',
        },
        bull: {
          bright: '#00FF88',
          DEFAULT: '#00E676',
          muted: '#00C853',
          dim: '#1B5E20',
        },
        bear: {
          bright: '#FF3D71',
          DEFAULT: '#FF1744',
          muted: '#D50000',
          dim: '#4A1525',
        },
        neutral: {
          bright: '#FFD740',
          DEFAULT: '#FFC107',
          muted: '#FF8F00',
          dim: '#3E2723',
        },
        // Legacy aliases for compatibility
        success: '#00E676',
        error: '#FF1744',
        warning: '#FFC107',
        onSurface: '#E8ECF1',
        onSurfaceMuted: '#8B95A5',
        onSurfaceDim: '#505A6B',
        // Agent colors
        agent: {
          fii: '#FF6B6B',
          dii: '#00E676',
          retail: '#FFD740',
          algo: '#00D4E0',
          promoter: '#BB86FC',
          rbi: '#448AFF',
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'Fira Code', 'monospace'],
        display: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
      },
      backdropBlur: {
        xs: '4px',
      },
      borderRadius: {
        xl: '12px',
        '2xl': '16px',
      },
      spacing: {
        '18': '4.5rem',
        '22': '5.5rem',
      },
      boxShadow: {
        'glow-sm': '0 0 8px rgba(0,212,224,0.15)',
        'glow': '0 0 16px rgba(0,212,224,0.2)',
        'glow-lg': '0 0 32px rgba(0,212,224,0.25)',
        'glow-bull': '0 0 16px rgba(0,230,118,0.2)',
        'glow-bear': '0 0 16px rgba(255,23,68,0.2)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'scanline': 'scanline 2s linear infinite',
      },
      keyframes: {
        scanline: {
          '0%': { opacity: '0.05' },
          '50%': { opacity: '0.1' },
          '100%': { opacity: '0.05' },
        },
      },
    },
  },
  plugins: [],
}
