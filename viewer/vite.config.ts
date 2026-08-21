import { defineConfig, type Plugin } from 'vite'
import { createReadStream, existsSync, statSync } from 'node:fs'
import { join, normalize, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = fileURLToPath(new URL('.', import.meta.url))
// PMTiles と dataset.json はリポジトリ直下 data/ に置かれる。
const DATA_DIR = resolve(rootDir, '..', 'data')

/**
 * 開発サーバーで data/*.pmtiles を Range(206) 対応で配信するミドルウェア。
 * pmtiles.js は HTTP Byte Serving を要求するため、これがないとタイルを読めない。
 * 本番では PMTiles を同梱するか Release アセットを直接読む（どちらも Range 対応）。
 */
function dataDevServer(): Plugin {
  return {
    name: 'data-dev-server',
    configureServer(server) {
      server.middlewares.use('/data', (req, res, next) => {
        try {
          const urlPath = decodeURIComponent((req.url ?? '').split('?')[0])
          const rel = normalize(urlPath).replace(/^([/\\]|\.\.[/\\])+/, '')
          const file = join(DATA_DIR, rel)
          if (!file.startsWith(DATA_DIR) || !existsSync(file)) {
            res.statusCode = 404
            res.end('Not found')
            return
          }
          const size = statSync(file).size
          res.setHeader('Accept-Ranges', 'bytes')
          res.setHeader('Access-Control-Allow-Origin', '*')
          res.setHeader(
            'Content-Type',
            file.endsWith('.json') ? 'application/json' : 'application/octet-stream',
          )
          const m = req.headers.range ? /bytes=(\d*)-(\d*)/.exec(req.headers.range) : null
          if (m) {
            const start = m[1] ? parseInt(m[1], 10) : 0
            let end = m[2] ? parseInt(m[2], 10) : size - 1
            end = Math.min(end, size - 1)
            if (start > end || start >= size) {
              res.statusCode = 416
              res.setHeader('Content-Range', `bytes */${size}`)
              res.end()
              return
            }
            res.statusCode = 206
            res.setHeader('Content-Range', `bytes ${start}-${end}/${size}`)
            res.setHeader('Content-Length', String(end - start + 1))
            createReadStream(file, { start, end }).pipe(res)
            return
          }
          res.statusCode = 200
          res.setHeader('Content-Length', String(size))
          createReadStream(file).pipe(res)
        } catch (err) {
          next(err)
        }
      })
    },
  }
}

export default defineConfig({
  base: './',
  plugins: [dataDevServer()],
  server: { port: 8001 },
  define: {
    __BUILD_TIME__: JSON.stringify(
      new Date().toISOString().replace('T', ' ').slice(0, 16) + ' UTC',
    ),
  },
})
