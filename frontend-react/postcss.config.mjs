const config = {
  plugins: {
    // postcss-import MUST come first so it resolves `@import "tailwindcss"`
    // via Node.js module resolution anchored to the CSS file's own directory.
    // This prevents Turbopack from trying (and failing) to resolve the bare
    // specifier from the workspace root where node_modules doesn't exist.
    "postcss-import": {},
    "@tailwindcss/postcss": {},
  },
};

export default config;
