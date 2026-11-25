/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"] },
      colors: {
        brand: { 50: "#EEF2FF", 100: "#E0E7FF", 200: "#C7D2FE", 500: "#6366F1", 600: "#4F46E5", 700: "#4338CA" },
        page: "#F5F6FA",
      },
      boxShadow: { card: "0 1px 2px rgba(16,24,40,.05), 0 1px 3px rgba(16,24,40,.06)" },
    },
  },
  plugins: [],
};
