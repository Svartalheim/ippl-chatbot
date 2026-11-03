/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          dark: "#141413",
          card: "#1e1e1d",
          red: "#C92A2A",
          redHover: "#A61E1E",
          grayText: "#9E9E9C",
          border: "#2C2C2A",
        },
      },
    },
  },
  plugins: [],
};
