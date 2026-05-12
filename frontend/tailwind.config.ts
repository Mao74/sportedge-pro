import type { Config } from 'tailwindcss';

/**
 * Tailwind v3.4 configuration. Colors are mapped to CSS variables defined in
 * `src/styles/global.css` so dark/light themes swap by toggling
 * `data-theme` on <html>.
 */
const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: {
          base: 'var(--bg-base)',
          elevated: 'var(--bg-elevated)',
          overlay: 'var(--bg-overlay)',
          hover: 'var(--bg-hover)',
        },
        border: {
          subtle: 'var(--border-subtle)',
          strong: 'var(--border-strong)',
          focus: 'var(--border-focus)',
        },
        text: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          tertiary: 'var(--text-tertiary)',
        },
        accent: {
          gain: 'var(--accent-gain)',
          'gain-bg': 'var(--accent-gain-bg)',
          loss: 'var(--accent-loss)',
          'loss-bg': 'var(--accent-loss-bg)',
          warn: 'var(--accent-warn)',
          'warn-bg': 'var(--accent-warn-bg)',
          info: 'var(--accent-info)',
          'info-bg': 'var(--accent-info-bg)',
          brand: 'var(--accent-brand)',
          'brand-bg': 'var(--accent-brand-bg)',
        },
        strat: {
          'magic-cs': 'var(--strat-magic-cs)',
          'draw-hunter': 'var(--strat-draw-hunter)',
          'custom-1': 'var(--strat-custom-1)',
          'custom-2': 'var(--strat-custom-2)',
          'custom-3': 'var(--strat-custom-3)',
          'custom-4': 'var(--strat-custom-4)',
          'custom-5': 'var(--strat-custom-5)',
          'custom-6': 'var(--strat-custom-6)',
        },
      },
      fontFamily: {
        sans: ['Geist', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        '2xs': ['11px', { lineHeight: '1.5' }],
        xs: ['12px', { lineHeight: '1.5' }],
        sm: ['13px', { lineHeight: '1.5' }],
        base: ['15px', { lineHeight: '1.5' }],
        lg: ['18px', { lineHeight: '1.4' }],
        xl: ['24px', { lineHeight: '1.2', letterSpacing: '-0.01em' }],
        '2xl': ['32px', { lineHeight: '1.2', letterSpacing: '-0.01em' }],
        '3xl': ['48px', { lineHeight: '1.1', letterSpacing: '-0.01em' }],
      },
      fontWeight: {
        normal: '400',
        medium: '500',
      },
      borderRadius: {
        lg: '8px',
        xl: '12px',
      },
      transitionTimingFunction: {
        'spring-out': 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
    },
  },
  plugins: [],
};

export default config;
