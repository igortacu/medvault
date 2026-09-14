export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#E9EEF5',
          100: '#C7D3E5',
          300: '#5B7CA8',
          500: '#1E3A66', // sampled from header / hero background
          600: '#152C52', // sampled from header / hero background
          700: '#101F3D',
          900: '#0A1526',
        },
        accent: {
          50: '#E4F6FC',
          200: '#9EDBF0',
          400: '#29ABE2', // sampled from icons / links / highlights
          500: '#1C93C7',
          600: '#1476A1',
        },
        coral: {
          400: '#F7924E', // "BOOK NOW" CTA button
          500: '#F07A2E',
        },
        sky: {
          300: '#BFE1F5',
          400: '#8FCBEE', // light section accents / bubble graphics
          500: '#5FB1E4',
        },
        sage: {
          400: '#4E7C99', // secondary icon tone
          500: '#3C6580',
        },
        ink: {
          900: '#132434', // headings
          600: '#4B5B6B', // body copy
          400: '#8B98A3', // muted / secondary text
        },
      },
      fontFamily: {
        display: ['Sora', 'sans-serif'], // headline weight, e.g. "We Ensure Safe Diagnoses"
        sans: ['Inter', 'sans-serif'], // body copy, nav, cards
      },
      borderRadius: {
        card: '1.5rem', // 24px — matches card corners in the reference
        pill: '9999px', // CTA buttons
      },
      boxShadow: {
        card: '0 8px 24px -8px rgba(21, 44, 82, 0.15)',
      },
    },
  },
  plugins: [],
};
