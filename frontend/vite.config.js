import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    include: ['plotly.js', 'react-plotly.js'],
  },
  build: {
    commonjsOptions: {
      include: [/plotly\.js/, /node_modules/],
    },
  },
})
