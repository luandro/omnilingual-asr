import { defineConfig } from "cf/config";

// NOTE: this new-config format cannot yet express D1 bindings (wrangler 4.146
// schema rejects a `d1`/`bindings` key at worker level). Deploying with the cf
// CLI uploads this worker WITHOUT env.DB, which breaks POST /feedback.
// Use `npx wrangler deploy` (wrangler.toml has the [[d1_databases]] binding)
// until wrangler's new-config schema grows D1 support.
export default defineConfig({
  worker: {
    name: "matses-asr-proxy",
    entrypoint: "./src/worker.js",
    compatibilityDate: "2026-09-01",
  },
});
