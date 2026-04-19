import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.tasdcrc.eczemalog',
  appName: 'EczemaLog',
  webDir: '../backend/static',
  server: {
    // Dev mode: load from Vite dev server for hot reload.
    // The Vite proxy forwards /api requests to the backend.
    // Comment out for production builds (loads from webDir instead).
    url: 'https://felix-xps-15-9520.tail63d27c.ts.net',
    cleartext: true,
  },
};

export default config;
