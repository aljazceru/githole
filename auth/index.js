const http = require('http');

const PORT = process.env.AUTH_PORT || 3000;
// used for pass through
const TARGET_HOST = process.env.TARGET_HOST || 'localhost';
const TARGET_PORT = process.env.TARGET_PORT || 8080;

// is consumed by home dependency
const GIT_PEAR= process.env.GIT_PEAR || '/srv/repos/pear'

const GIT_PEAR_CODE = process.env.GIT_PEAR_CODE || '/app/gitpear'
const ALC = require(`${GIT_PEAR_CODE}/src/acl`)
const auth = require(`${GIT_PEAR_CODE}/src/auth/nip98`)
const home = require(`${GIT_PEAR_CODE}/src/home`)
const ACL = require(`${GIT_PEAR_CODE}/src/acl`)

const server = http.createServer(async (req, res) => {
  const { method, url } = req;

  const repoName = url.split('/').filter(Boolean)[0];
  const action = url.split('/').filter(Boolean).pop();
  if (!repoName || !action) {
    console.error('Invalid URL');
    res.writeHead(403);
    return res.end();
  }

  let body = [];
  req.on('data', (chunk) => { body.push(chunk); })
  req.on('end', async () => {
    body = Buffer.concat(body);

    if (method !== 'POST' || action !== 'git-receive-pack') {
      return await passThrough(req, res, body);
    } else {
      return await authenticatedPassThrough(req, res, body, repoName);
    }
  });
});

async function authenticatedPassThrough(req, res, body, repoName) {
  let authHeader;
  let url;
  try {
    const res = parseHeaders(req.headers);
    console.log(res)
    url = res.url;
    authHeader = res.authHeader;
  } catch (e) {
    console.error(e)
    res.writeHead(403);
    return res.end();
  }

  let commit;
  let branch;
  try {
    const res = parseBody(body);
    commit = res.commit;
    branch = res.branch;
  } catch (e) {
    console.error(e)
    res.writeHead(403);
    return res.end();
  }

  let userId;
  try {
    const event = await auth.getId({
      payload: authHeader,
      url,
      method: 'push',
      data: commit,
    })
    userId = event.userId;
  } catch (e) {
    console.error(e);
    res.writeHead(403);
    return res.end();
  }

  try {
    validateACL(userId, repoName, branch);
  } catch (e) {
    console.error(e);
    res.writeHead(403);
    return res.end();
  }

  return passThrough(req, res, body);
}

function validateACL(userId, repoName, branch) {
  if (!home.isInitialized(repoName) || !home.isShared(repoName)) {
    throw new Error('Repo not initialized or not shared');
  }

  const isContributor = ACL.getContributors(repoName).includes(userId)
  if (!isContributor) {
    throw new Error(`User is not a contributor: ${userId}`);
  }

  const isProtectedBranch = ACL.getACL(repoName).protectedBranches.includes(branch)
  const isAdmin = ACL.getAdmins(repoName).includes(userId)
  if (isProtectedBranch && !isAdmin) {
    throw new Error(`Branch ${branch} is protected and user ${userId} is not an admin`);
  }
}

function parseBody(body) {
  const bodyString = body.toString();
  const commit = bodyString.split(' ')[1];
  const branch = bodyString.split(' ')[2].split('/').pop();
  return { commit, branch };
}

function parseHeaders(headers) {
  let authHeader = headers['X-Authorization'];
  authHeader = authHeader || headers['x-authorization'];
  if (!authHeader.includes('Nostr')) {
    throw new Error('Invalid auth header');
  }
  authHeader = authHeader.split(' ')[1];

  let url = headers['X-Original-URI'];
  url = url || headers['x-original-uri'];
  url = url.replace('/git-receive-pack', '')

  return { authHeader, url };
}


async function passThrough(req, res, body) {
  const options = {
      hostname: 'localhost',
      port: 8080,
      path: req.url,
      method: req.method,
      headers: req.headers
  };

  const proxyReq = http.request(options, (proxyRes) => {
    res.writeHead(proxyRes.statusCode, proxyRes.headers);
    proxyRes.pipe(res);
  });

  proxyReq.on('error', (err) => {
    console.error('error:', err);
    res.statusCode = 500;
    res.end('Proxy Error');
  });

  proxyReq.write(body);
  proxyReq.end();
}

server.listen(3000, () => {
  console.log('Server running on port 3000');
});
