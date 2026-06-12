// esbuild configuration for Alpine.js TypeScript pages.
// Compiles pages to dist/assets/<page>.js as IIFE bundles.
// Run: node esbuild.config.mjs
import * as esbuild from 'esbuild'
import { existsSync, mkdirSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const outDir = resolve(__dirname, 'dist', 'assets')

// Ensure output directory exists
if (!existsSync(outDir)) {
  mkdirSync(outDir, { recursive: true })
}

/** @type {esbuild.BuildOptions} */
const sharedOptions = {
  bundle: true,
  minify: true,
  sourcemap: false,
  target: ['es2020'],
  format: 'iife',
  // Alpine.js is loaded from CDN in templates, so alpine is external
  external: [],
}

const pages = [
  {
    entry: resolve(__dirname, 'src', 'pages', 'login.ts'),
    outName: 'login',
  },
  {
    entry: resolve(__dirname, 'src', 'pages', 'dashboard.ts'),
    outName: 'dashboard',
  },
  {
    entry: resolve(__dirname, 'src', 'pages', 'schema.ts'),
    outName: 'schema',
  },
  {
    entry: resolve(__dirname, 'src', 'pages', 'jobs.ts'),
    outName: 'jobs',
  },
]

async function buildAll() {
  // Build Alpine pages concurrently
  const results = await Promise.all(
    pages.map((page) =>
      esbuild.build({
        ...sharedOptions,
        entryPoints: [page.entry],
        outfile: resolve(outDir, `${page.outName}.js`),
      }),
    ),
  )

  // Also build apiClient as a global bundle (exposes window.schemaApi etc.)
  await esbuild.build({
    ...sharedOptions,
    entryPoints: [resolve(__dirname, 'src', 'api', 'apiClient.ts')],
    outfile: resolve(outDir, 'apiClient.js'),
    define: {
      // Ensure window exports work in IIFE format
    },
  })

  // Copy styles.css to dist/assets
  await esbuild.build({
    ...sharedOptions,
    entryPoints: [resolve(__dirname, 'src', 'styles', 'styles.css')],
    outfile: resolve(outDir, 'styles.css'),
    loader: { '.css': 'copy' },
  })

  console.log(`✅ Built ${pages.length + 2} bundles to ${outDir}`)
  return results
}

buildAll().catch((err) => {
  console.error('❌ Build failed:', err)
  process.exit(1)
})
