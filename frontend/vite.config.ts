import { defineConfig } from 'vite';
export default defineConfig({server:{proxy:{'/advisor':{target:'http://advisor:8003',changeOrigin:true,rewrite:path=>path.replace(/^\/advisor/,'')}}}});
