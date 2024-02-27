const http = require('http');
const { URL } = require('url');

const DEFAULT_PORT = 3000;

const server = http.createServer((req, res) => {
  const authHeader = req.headers['X-Authorization'];
  if (authHeader) {
    const event = JSON.parse(Buffer.from(authHeader, 'base64').toString())
  }

  const url = req.headers['x-original-uri']
  const method = req.headers['x-original-method']
  if (!url || !method) {
    res.writeHead(403);
    return res.end();
  }

  const repoName = url.split('/').filter(Boolean)[0];
  const action = url.split('/').filter(Boolean).pop();
  if (!repoName || !action) {
    res.writeHead(403);
    return res.end();
  }

  if (method !== 'POST' || action !== 'git-receive-pack') {
    res.writeHead(200);
    return res.end();
  }

  console.log(`Will do auth in ${repoName} for ${action}`);

  res.writeHead(200);
  res.end();
})

server.listen(DEFAULT_PORT, () => {
  console.log(`Server is running on http://localhost:${DEFAULT_PORT}`);
})
