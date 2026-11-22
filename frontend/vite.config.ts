import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    server: {
      proxy: {
        "/api/single-agent": {
          target:
            environment.SINGLE_AGENT_API_PROXY_TARGET ??
            "http://127.0.0.1:8011",
          rewrite: (path) => path.replace(/^\/api\/single-agent/, "/api"),
        },
        "/api/multi-agent": {
          target:
            environment.MULTI_AGENT_API_PROXY_TARGET ?? "http://127.0.0.1:8012",
          rewrite: (path) => path.replace(/^\/api\/multi-agent/, "/api"),
        },
      },
    },
  };
});
