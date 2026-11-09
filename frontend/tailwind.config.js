/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          50: '#f2f6fb', 100: '#e3ebf6', 200: '#c6d7ec', 300: '#96b5da',
          400: '#5f8cc3', 500: '#3d6cac', 600: '#2d548c', 700: '#264472',
          800: '#213a5e', 900: '#142943', 950: '#0b1a2e',
        },
        teal: {
          50: '#effcf9', 100: '#d5f7ef', 200: '#acece0', 300: '#78dccc',
          400: '#40c3b2', 500: '#20a89a', 600: '#15877e', 700: '#146c66',
          800: '#155753', 900: '#154945', 950: '#062c2b',
        },
        ink: '#0f172a',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        display: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        panel: '0 12px 34px -18px rgba(11, 26, 46, 0.35)',
        glow: '0 0 0 1px rgba(32,168,154,0.18), 0 18px 50px -24px rgba(32,168,154,0.55)',
      },
      keyframes: {
        fadeUp: { '0%': { opacity: '0', transform: 'translateY(10px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        pulseSoft: { '0%, 100%': { opacity: '0.65' }, '50%': { opacity: '1' } },
      },
      animation: {
        fadeUp: 'fadeUp 0.45s ease-out both',
        pulseSoft: 'pulseSoft 2.8s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
