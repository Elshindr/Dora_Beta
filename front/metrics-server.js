const client = require('prom-client');
const express = require('express');
const app = express();

client.collectDefaultMetrics();

app.get('/metrics', async (req, res) => {
  res.set('Content-Type', client.register.contentType);
  res.end(await client.register.metrics());
});

app.listen(9091, () => console.log("App running at http://localhost:9091"));