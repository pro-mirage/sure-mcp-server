# Sure MCP Server

A Model Context Protocol (MCP) server for integrating with the [Sure](https://github.com/we-promise/sure) self-hosted personal finance platform. It exposes a Streamable HTTP endpoint for remote clients such as Hermes Agent.

## Quick Start

There are two ways to run the Sure MCP Server: **Docker (recommended)** or **manual installation**. In both cases the MCP endpoint is `http://localhost:8000/mcp` and the health endpoint is `http://localhost:8000/health`.

### Option A: Docker Installation (Recommended)

1. Copy `.env.example` to `.env` and set at least:

   ```env
   SURE_API_URL=http://host.docker.internal:3000
   SURE_API_KEY=your-api-key-here
   MCP_AUTH_TOKEN=generate-a-long-random-secret
   ```

2. **Build and start the Docker image**:

   ```bash
   docker compose up --build -d
   ```

3. Confirm that `curl http://localhost:8000/health` returns `{"status":"ok",...}`.

### Option B: Manual Installation

1. **Clone this repository**:
   ```bash
   git clone https://github.com/pro-mirage/sure-mcp-server.git
   cd sure-mcp-server
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

3. Configure the environment and start the HTTP server:

   ```bash
   export SURE_API_URL=http://localhost:3000
   export SURE_API_KEY=your-api-key-here
   export MCP_AUTH_TOKEN=generate-a-long-random-secret
   sure-mcp-server
   ```

### Connect Hermes Agent

Add the deployed endpoint to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  sure:
    url: "https://sure-mcp.example.com/mcp"
    headers:
      Authorization: "Bearer generate-a-long-random-secret"
    timeout: 120
    connect_timeout: 30
```

Tool names in Hermes are prefixed with the server name, for example `mcp_sure_get_accounts`.

### Deploy on Coolify

Deploy this repository as a single **Application** using the **Dockerfile** build pack. Set the container port to `8000`, health check path to `/health`, and point the public domain at port `8000`. See [COOLIFY.md](COOLIFY.md) for the complete setup.

### Get Your Sure API Key

1. Start your Sure Docker instance: `docker compose up -d`
2. Log into Sure at `http://localhost:3000`
3. Go to **Settings > API Key** and generate a new key
4. Add the API key to the Sure MCP server environment

### Start Using in Hermes

Once configured, use these tools through Hermes:
- `get_accounts` - View all accounts
- `get_transactions` - Recent transactions
- `get_categories` - Transaction categories
- `sync_accounts` - Trigger account sync

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `setup_authentication` | Get setup instructions | None |
| `check_auth_status` | Check authentication status | None |
| `check_connection` | Test API connection | None |
| `get_accounts` | Get all financial accounts | None |
| `get_transactions` | Get transactions with filtering | `limit`, `start_date`, `end_date`, `account_ids`, `category_ids`, `search` |
| `get_transaction` | Get single transaction | `transaction_id` |
| `create_transaction` | Create new transaction | `account_id`, `amount`, `name`, `date`, `category_id`, `notes`, `nature` |
| `update_transaction` | Update transaction | `transaction_id`, `amount`, `name`, `date`, `category_id`, `notes` |
| `delete_transaction` | Delete transaction | `transaction_id` |
| `get_categories` | Get all categories | None |
| `get_category` | Get single category | `category_id` |
| `sync_accounts` | Trigger account sync | None |
| `get_usage` | Get API usage info | None |
| `list_chats` | List AI chat sessions | None |
| `create_chat` | Create new chat | `title` |
| `get_chat` | Get chat details | `chat_id` |
| `send_message` | Send message to AI | `chat_id`, `content` |
| `delete_chat` | Delete chat session | `chat_id` |

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SURE_API_URL` | Yes | - | Base URL of your Sure instance |
| `SURE_API_KEY` | One auth method required | - | API key from Sure settings |
| `SURE_ACCESS_TOKEN` | One auth method required | - | Alternative Sure bearer token |
| `SURE_TIMEOUT` | No | 30 | Request timeout in seconds |
| `SURE_VERIFY_SSL` | No | true | Verify SSL certificates |
| `MCP_HOST` | No | 0.0.0.0 | HTTP bind address |
| `PORT` | No | 8000 | HTTP listen port |
| `MCP_PATH` | No | /mcp | Streamable HTTP endpoint path |
| `MCP_JSON_RESPONSE` | No | true | Return JSON rather than an SSE body for each response |
| `MCP_STATELESS_HTTP` | No | true | Avoid server-side session affinity |
| `MCP_AUTH_TOKEN` | Recommended | - | Bearer token required from MCP clients when set |

For Docker connecting to Sure on the host machine, use `SURE_API_URL=http://host.docker.internal:3000`. Set `SURE_VERIFY_SSL=false` only for a trusted development endpoint with a self-signed certificate.

## Date Formats

- All dates should be in `YYYY-MM-DD` format (e.g., "2024-12-15")
- Transaction amounts: use `nature` field to specify "income" or "expense"

## Troubleshooting

### Connection Issues
1. Verify `/health` responds successfully.
2. Verify the client URL includes `/mcp`.
3. Check that the Hermes `Authorization` header matches `MCP_AUTH_TOKEN`.
4. Check the Sure API URL and use `check_connection` to diagnose upstream access.

### `mcp.server.fastmcp` import error

The application uses the MCP 1.x `FastMCP` API. Both dependency files deliberately constrain the SDK to v1; rebuild the Docker image without cache if an older layer installed MCP 2.x.

### Authentication Issues
1. Verify your API key is correct
2. Check the key hasn't expired
3. Regenerate the key in Sure settings

## Project Structure

```
sure-mcp-server/
├── src/sure_mcp_server/
│   ├── __init__.py
│   └── server.py         # Main server implementation
├── pyproject.toml
├── requirements.txt
├── COOLIFY.md
├── Dockerfile
├── docker-compose.yml
├── tests/
└── README.md
```

## License

MIT License
