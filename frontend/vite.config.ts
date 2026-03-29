import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'

const certsDir = path.resolve(__dirname, '../certs')
const certFiles = fs.existsSync(certsDir)
  ? fs.readdirSync(certsDir).filter(f => f.endsWith('.crt'))
  : []
const httpsConfig = certFiles.length > 0
  ? {
      cert: fs.readFileSync(path.join(certsDir, certFiles[0])),
      key: fs.readFileSync(path.join(certsDir, certFiles[0].replace('.crt', '.key'))),
    }
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
