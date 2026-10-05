import { defineConfig } from "@playwright/test";

const API_URL = "http://127.0.0.1:8001";
const WEB_PORT = 3105;

export default defineConfig({
  testDir: "./e2e",
  timeout: 90000,
  retries: 0,
  use: { baseURL: `http://127.0.0.1:${WEB_PORT}`, headless: true },
  webServer: [
    {
      command: "../backend/.venv/bin/python -m uvicorn app.main:app --port 8001",
      cwd: "../backend",
      url: `${API_URL}/health`,
      timeout: 60000,
      reuseExistingServer: false,
      env: {
        ...process.env,
        DATA_DIR: "/tmp/thedaaakhouse-e2e/data",
        DATABASE_URL: "sqlite:////tmp/thedaaakhouse-e2e/e2e.db",
        CORS_ORIGINS: "http://localhost:3000,http://localhost:3100,http://127.0.0.1:3105,http://localhost:3105",
      } as Record<string, string>,
    },
    {
      command: `npm run dev -- -p ${WEB_PORT}`,
      url: `http://127.0.0.1:${WEB_PORT}/login`,
      timeout: 120000,
      reuseExistingServer: false,
      env: { ...process.env, NEXT_PUBLIC_API_URL: API_URL } as Record<string, string>,
    },
  ],
});
