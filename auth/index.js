const http = require('http');
const { URL } = require('url');

const DEFAULT_PORT = 3000;

const server = http.createServer((req, res) => {
  const authHeader = req.headers['X-Authorization'];
  if (authHeader) {
    const event = JSON.parse(Buffer.from(authHeader, 'base64').toString())
  }

  // TODO: validate event
  
  const { method, url } = req;
  console.log(`Received ${method} request on ${url}`);

  res.writeHead(200);
  res.end();
})

server.listen(DEFAULT_PORT, () => {
  console.log(`Server is running on http://localhost:${DEFAULT_PORT}`);
})
