# Coolify deployment

Deploy the Sure MCP server as one Dockerfile-based application. Docker Compose is not required for Coolify because this repository contains only one service.

## Application settings

- Source: this Git repository and branch
- Build pack: Dockerfile
- Dockerfile location: `./Dockerfile`
- Container port: `8000`
- Health check path: `/health`
- Health check method: `GET`
- Public domain: for example `https://sure-mcp.example.com`

The MCP client URL includes the path: `https://sure-mcp.example.com/mcp`.

## Environment variables

Set these in Coolify:

```env
SURE_API_URL=https://your-sure-instance.example.com
SURE_API_KEY=your-sure-api-key
SURE_TIMEOUT=30
SURE_VERIFY_SSL=true
MCP_HOST=0.0.0.0
PORT=8000
MCP_PATH=/mcp
MCP_JSON_RESPONSE=true
MCP_STATELESS_HTTP=true
MCP_AUTH_TOKEN=generate-a-separate-long-random-secret
```

`MCP_AUTH_TOKEN` protects the remotely callable MCP tools. It should be a separate secret from the Sure API key. Coolify terminates HTTPS at its proxy; the container itself listens on HTTP port 8000.

## Deploy and verify

Trigger a deployment with the build cache disabled the first time after upgrading from the broken MCP 2.x image. The logs should show the server listening on `0.0.0.0:8000` with an endpoint at `/mcp`.

Verify the public health endpoint:

```bash
curl --fail https://sure-mcp.example.com/health
```

An unauthenticated request to `/mcp` should return `401` when `MCP_AUTH_TOKEN` is configured. Hermes supplies the token:

```yaml
mcp_servers:
  sure:
    url: "https://sure-mcp.example.com/mcp"
    headers:
      Authorization: "Bearer generate-a-separate-long-random-secret"
    timeout: 120
    connect_timeout: 30
```

Restart Hermes after changing its configuration. On startup it should discover tools such as `mcp_sure_get_accounts` and `mcp_sure_get_transactions`.
