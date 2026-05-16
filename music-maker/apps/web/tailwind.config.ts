import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}',
  ],
  theme: {
    container: {
      center: true,
      padding: '1rem',
      screens: {
        '2xl': '1440px',
      },
    },
    extend: {
      colors: {
        // 02-UX-Design 4.1 컬러 토큰 (CSS 변수로 매핑)
        canvas: 'hsl(var(--bg-canvas))',
        surface: 'hsl(var(--bg-surface))',
        elevated: 'hsl(var(--bg-elevated))',
        border: 'hsl(var(--border-subtle))',
        foreground: 'hsl(var(--text-primary))',
        muted: {
          DEFAULT: 'hsl(var(--bg-elevated))',
          foreground: 'hsl(var(--text-secondary))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent-primary))',
          hover: 'hsl(var(--accent-hover))',
          foreground: 'hsl(var(--text-primary))',
        },
        success: 'hsl(var(--state-success))',
        warning: 'hsl(var(--state-warning))',
        danger: 'hsl(var(--state-danger))',
        wave: 'hsl(var(--viz-wave))',
        'wave-played': 'hsl(var(--viz-wave-played))',
        // shadcn fallback aliases
        background: 'hsl(var(--bg-canvas))',
        primary: {
          DEFAULT: 'hsl(var(--accent-primary))',
          foreground: 'hsl(var(--text-primary))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--bg-elevated))',
          foreground: 'hsl(var(--text-primary))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--state-danger))',
          foreground: 'hsl(var(--text-primary))',
        },
        input: 'hsl(var(--border-subtle))',
        ring: 'hsl(var(--accent-primary))',
        card: {
          DEFAULT: 'hsl(var(--bg-surface))',
          foreground: 'hsl(var(--text-primary))',
        },
        popover: {
          DEFAULT: 'hsl(var(--bg-elevated))',
          foreground: 'hsl(var(--text-primary))',
        },
      },
      borderRadius: {
        sm: '8px',
        md: '12px',
        lg: '20px',
      },
      fontFamily: {
        sans: ['Inter', 'Pretendard', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        'display-lg': ['56px', { lineHeight: '1.1', fontWeight: '700' }],
        'display-md': ['40px', { lineHeight: '1.15', fontWeight: '700' }],
        'heading-lg': ['28px', { lineHeight: '1.2', fontWeight: '600' }],
        'heading-md': ['22px', { lineHeight: '1.3', fontWeight: '600' }],
        'body-lg': ['17px', { lineHeight: '1.6', fontWeight: '400' }],
        'body-md': ['15px', { lineHeight: '1.55', fontWeight: '400' }],
        'body-sm': ['13px', { lineHeight: '1.5', fontWeight: '400' }],
      },
      keyframes: {
        ripple: {
          '0%': { transform: 'scale(1)', opacity: '0.6' },
          '100%': { transform: 'scale(1.4)', opacity: '0' },
        },
        shake: {
          '0%, 100%': { transform: 'translateX(0)' },
          '25%': { transform: 'translateX(-4px)' },
          '75%': { transform: 'translateX(4px)' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
      },
      animation: {
        ripple: 'ripple 2s ease-out infinite',
        shake: 'shake 0.4s ease-in-out',
        'fade-in': 'fade-in 0.3s ease-out',
      },
      boxShadow: {
        glow: '0 0 0 4px hsl(var(--accent-primary) / 0.35)',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};

export default config;
