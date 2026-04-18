/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // ── Surface hierarchy (Algon.iq — clean whites/creams) ──
        surface: {
          0: '#FFFFFF',
          1: '#FAFAFA',
          2: '#F5F5F5',
          3: '#EEEEEE',
          4: '#E0E0E0',
        },
        // ── Primary: Algon Red ──
        primary: {
          glow: '#E8192F',
          DEFAULT: '#CC152B',
          muted: '#A81123',
          dim: '#7A0C19',
          deep: '#4D0810',
        },
        // ── Secondary: Dark (for hover states, footer-style sections) ──
        secondary: {
          DEFAULT: '#141010',
          muted: '#2A2626',
          dim: '#3D3838',
        },
        // ── Trading signals: green/red (kept functional) ──
        bull: {
          bright: '#16A34A',
          DEFAULT: '#059669',
          muted: '#047857',
          dim: '#ECFDF5',
        },
        bear: {
          bright: '#EF4444',
          DEFAULT: '#DC2626',
          muted: '#B91C1C',
          dim: '#FEF2F2',
        },
        neutral: {
          bright: '#F59E0B',
          DEFAULT: '#D97706',
          muted: '#B45309',
          dim: '#FFFBEB',
        },
        // ── Text hierarchy (dark on light) ──
        onSurface: '#1A1A1A',
        onSurfaceMuted: '#6B7280',
        onSurfaceDim: '#9CA3AF',
        // ── Semantic ──
        success: '#059669',
        error: '#DC2626',
        warning: '#D97706',
        // ── Agent colors (adjusted for light bg contrast) ──
        agent: {
          fii: '#DC2626',
          dii: '#059669',
          retail: '#D97706',
          algo: '#CC152B',
          promoter: '#7C3AED',
          rbi: '#2563EB',
          options: '#EA580C',
          news: '#DB2777',
        },
      },
      fontFamily: {
        sans: ['Geist Sans', 'Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        mono: ['Geist Mono', 'SF Mono', 'JetBrains Mono', 'monospace'],
        display: ['Geist Sans', 'Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
      },
      backdropBlur: {
        xs: '4px',
      },
      borderRadius: {
        xl: '12px',
        '2xl': '16px',
        'pill': '100px',
      },
      spacing: {
        '18': '4.5rem',
        '22': '5.5rem',
      },
      boxShadow: {
        'sm': '0 1px 3px rgba(0,0,0,0.08)',
        'card': '0 7px 29px 0 rgba(0,0,0,0.08)',
        'card-hover': '0 12px 40px 0 rgba(0,0,0,0.15)',
        'card-lg': '0 7px 29px 0 rgba(0,0,0,0.12)',
        'elevated': '0 20px 60px rgba(0,0,0,0.12)',
        'btn': '0 2px 8px rgba(204,21,43,0.25)',
        'btn-hover': '0 4px 16px rgba(204,21,43,0.35)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'slide-up': 'slideUp 0.3s ease-out',
        'fade-in': 'fadeIn 0.4s ease-out',
        'flip-in': 'flipIn 0.4s ease-out',
      },
      keyframes: {
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        flipIn: {
          '0%': { opacity: '0', transform: 'perspective(600px) rotateX(-10deg)' },
          '100%': { opacity: '1', transform: 'perspective(600px) rotateX(0)' },
        },
      },
      fontSize: {
        'hero': 'clamp(3rem, 8vw, 8rem)',
        'hero-sm': 'clamp(1.5rem, 3vw, 3rem)',
        'display': 'clamp(2rem, 4vw, 4rem)',
      },
      letterSpacing: {
        'tight-display': '-0.05em',
      },
    },
  },
  plugins: [],
}
