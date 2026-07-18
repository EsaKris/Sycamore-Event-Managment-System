module.exports = {
  content: [
    '../apps/registrations/templates/public/**/*.html',
    '../apps/registrations/public_forms.py',
    '../apps/registrations/public_views.py',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        display: ['"Space Grotesk"', 'sans-serif'],
        sans: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
