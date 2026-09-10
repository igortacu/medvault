export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#E7F0EE',
          100: '#C4DCD6',
          300: '#5E9C8D',
          500: '#237A65',
          600: '#175B4C', // sampled from header / hero background
          700: '#134A3E',
          900: '#0B2D25',
        },
        accent: {
          50: '#FEF3E2',
          200: '#F7CD90',
          400: '#F2AD48', // sampled from "Healthcare" headline / buttons
          500: '#E8962A',
          600: '#C97A16',
        },
        coral: {
          400: '#F98987', // consultation card
          500: '#F26B69',
        },
        sky: {
          300: '#B7D6FB',
          400: '#93BEF5', // consultation card
          500: '#6FA3EE',
        },
        sage: {
          400: '#8CAFA8', // "For Client" card
          500: '#6F958D',
        },
        ink: {
          900: '#141A19', // headings
          600: '#4B5563', // body copy
          400: '#8A9490', // muted / secondary text
        },
      },
      fontFamily: {
        display: ['Sora', 'sans-serif'], // headline weight, e.g. "Healthcare"
        sans: ['Inter', 'sans-serif'], // body copy, nav, cards
      },
      borderRadius: {
        card: '1.5rem', // 24px — matches card corners in the reference
        pill: '9999px', // CTA buttons
      },
      boxShadow: {
        card: '0 8px 24px -8px rgba(23, 91, 76, 0.15)',
      },
    },
  },
  plugins: [],
};
