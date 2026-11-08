/**
 * Vitest config — L3 frontend unit/component layer (docs/03-test-plan.md §2).
 * Tests live in frontend/**\/__tests__/** per §2 layout.
 */
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  esbuild: {
    jsx: "automatic",
  },
  test: {
    environment: "jsdom",
    include: ["app/**/__tests__/**/*.test.{ts,tsx}", "__tests__/**/*.test.{ts,tsx}"],
  },
});
