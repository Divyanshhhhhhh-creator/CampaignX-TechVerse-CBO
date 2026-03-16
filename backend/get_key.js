const https = require('https');

const data = JSON.stringify({
  team_name: 'TechVerse',
  team_email: 'divyansh.shukla688@gmail.com'
});

// Try without servername first to bypass SNI if it's strictly failing
const options = {
  hostname: 'api.campaignx.com',
  port: 443,
  path: '/api/v1/signup',
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Content-Length': data.length
  },
  rejectUnauthorized: false,
  servername: '' // Empty servername to prevent sending SNI which might cause tlsv1 unrecognized name
};

const req = https.request(options, res => {
  let body = '';
  res.on('data', d => body += d);
  res.on('end', () => console.log("Response:", res.statusCode, body));
});

req.on('error', error => console.error("Error:", error.message));
req.write(data);
req.end();
