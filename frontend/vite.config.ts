import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'

const certsDir = path.resolve(__dirname, '../certs')
const certFile = path.join(certsDir, 'felixs-macbook-air.tail63d27c.ts.net.crt')
const keyFile = path.join(certsDir, 'felixs-macbook-air.tail63d27c.ts.net.key')
const httpsConfig = fs.existsSync(certFile) && fs.existsSync(keyFile)
  ? { cert: fs.readFileSync(certFile), key: fs.readFileSync(keyFile) }
  : undefined

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    https: httpsConfig,
    allowedHosts: ['.tail63d27c.ts.net'],
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  build: {
    outDir: '../backend/static',
    emptyOutDir: true,
  },
})
