import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Bloomberg Terminal inspired palette
        terminal: {
          bg: '#0a0a0a',
          panel: '#111111',
          border: '#2a2a2a',
          'border-bright': '#3a3a3a',
        },
        bloomberg: {
          orange: '#ff6b00',
          'orange-dim': '#cc5500',
          green: '#00d26a',
          'green-dim': '#00a854',
          red: '#ff3d3d',
          'red-dim': '#cc3131',
          yellow: '#ffd700',
          blue: '#0088ff',
          cyan: '#00d4ff',
        },
        text: {
          primary: '#ffffff',
          secondary: '#888888',
          muted: '#555555',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'SF Mono', 'Consolas', 'monospace'],
        display: ['Space Grotesk', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '0.875rem' }],
      },
      animation: {
        'pulse-fast': 'pulse 1s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'blink': 'blink 1.2s step-end infinite',
        'slide-up': 'slideUp 0.3s ease-out',
        'fade-in': 'fadeIn 0.2s ease-out',
      },
      keyframes: {
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};

export default config;
