import { createServer } from 'node:http'
import { createReadStream, existsSync } from 'node:fs'
import { extname, join } from 'node:path'
import handler from './dist/server/server.js'

const PORT = process.env.PORT || 3000
const HOST = process.env.HOST || '0.0.0.0'

const MIME_TYPES = {
  '.html': 'text/html',
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
}

createServer(async (req, res) => {
  // Serve static assets from dist/client
  const staticPath = join('dist/client', req.url.split('?')[0])
  if (existsSync(staticPath) && !staticPath.endsWith('/')) {
    const ext = extname(staticPath)
    res.writeHead(200, { 'Content-Type': MIME_TYPES[ext] || 'application/octet-stream' })
    createReadStream(staticPath).pipe(res)
    return
  }

  // Fall through to SSR handler
  const url = `http://${req.headers.host}${req.url}`
  const chunks = []
  for await (const chunk of req) chunks.push(chunk)
  const body = chunks.length && !['GET', 'HEAD'].includes(req.method)
    ? Buffer.concat(chunks)
    : undefined

  const request = new Request(url, {
    method: req.method,
    headers: req.headers,
    body,
    duplex: 'half',
  })

  const response = await handler.fetch(request)

  res.writeHead(response.status, Object.fromEntries(response.headers.entries()))

  if (response.body) {
    const reader = response.body.getReader()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      res.write(value)
    }
  }

  res.end()
}).listen(PORT, HOST, () => {
  console.log(`Server listening on http://${HOST}:${PORT}`)
})
