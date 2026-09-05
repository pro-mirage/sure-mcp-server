"""Sure MCP Server - Main server implementation."""

import json
import logging
import os
import secrets
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def get_bool_env(name: str, default: bool) -> bool:
    """Read a boolean environment variable."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


PORT = int(os.getenv("PORT", "8000"))
MCP_PATH = os.getenv("MCP_PATH", "/mcp")
if not MCP_PATH.startswith("/"):
    MCP_PATH = f"/{MCP_PATH}"

# Configure FastMCP for a remote, proxy-friendly Streamable HTTP deployment.
mcp = FastMCP(
    "Sure MCP Server",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=PORT,
    streamable_http_path=MCP_PATH,
    json_response=get_bool_env("MCP_JSON_RESPONSE", True),
    stateless_http=get_bool_env("MCP_STATELESS_HTTP", True),
)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(_request: Request) -> JSONResponse:
    """Return a lightweight liveness response for Coolify."""
    return JSONResponse({"status": "ok", "service": "sure-mcp-server"})


class BearerAuthMiddleware:
    """Optionally protect the MCP endpoint with a static bearer token."""

    def __init__(self, app: ASGIApp, path: str, token: str | None) -> None:
        self.app = app
        self.path = path.rstrip("/") or "/"
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request_path = scope.get("path", "").rstrip("/") or "/"
        if self.token and scope["type"] == "http" and request_path == self.path:
            headers = dict(scope.get("headers", []))
            supplied = headers.get(b"authorization", b"").decode("utf-8")
            expected = f"Bearer {self.token}"
            if not secrets.compare_digest(supplied, expected):
                response = JSONResponse(
                    {"error": "Unauthorized"},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


def get_api_url() -> str:
    """Get the Sure API base URL."""
    url = os.getenv("SURE_API_URL")
    if not url:
        raise RuntimeError(
            "❌ SURE_API_URL not configured. Set it in your environment."
        )
    return url.rstrip("/")


def get_auth_header() -> dict[str, str]:
    """Get authentication header for API requests."""
    api_key = os.getenv("SURE_API_KEY")
    access_token = os.getenv("SURE_ACCESS_TOKEN")

    if api_key:
        return {"X-Api-Key": api_key}
    elif access_token:
        return {"Authorization": f"Bearer {access_token}"}
    else:
        raise RuntimeError(
            "❌ No authentication configured. Set SURE_API_KEY or SURE_ACCESS_TOKEN."
        )


def get_client() -> httpx.Client:
    """Get configured HTTP client for Sure API."""
    timeout = int(os.getenv("SURE_TIMEOUT", "30"))
    verify_ssl = os.getenv("SURE_VERIFY_SSL", "true").lower() == "true"

    return httpx.Client(
        base_url=get_api_url(),
        timeout=timeout,
        verify=verify_ssl,
        headers=get_auth_header(),
    )


def handle_response(response: httpx.Response) -> Any:
    """Handle API response and raise appropriate errors."""
    if response.status_code == 401:
        raise RuntimeError("❌ Authentication failed. Check your API key.")
    elif response.status_code == 403:
        raise RuntimeError("❌ Permission denied. Check API key scopes.")
    elif response.status_code == 404:
        raise RuntimeError("❌ Resource not found.")
    elif response.status_code == 429:
        raise RuntimeError("❌ Rate limited. Please wait and try again.")
    elif response.status_code >= 400:
        raise RuntimeError(f"❌ API error {response.status_code}: {response.text}")

    if response.headers.get("content-type", "").startswith("application/json"):
        return response.json()
    return response.text


@mcp.tool()
def setup_authentication() -> str:
    """Get instructions for setting up authentication with Sure."""
    return """🔐 Sure MCP Server - Setup Instructions

1️⃣ Start your Sure Docker instance:
   cd /path/to/sure
   docker compose up -d

2️⃣ Log into Sure at http://localhost:3000

3️⃣ Go to Settings > API Key and generate a new key

4️⃣ Configure this server:
   SURE_API_URL=https://your-sure-instance.example.com
   SURE_API_KEY=your-api-key-here
   MCP_AUTH_TOKEN=generate-a-separate-long-random-secret

5️⃣ Add the remote endpoint to ~/.hermes/config.yaml:
   mcp_servers:
     sure:
       url: "https://sure-mcp.example.com/mcp"
       headers:
         Authorization: "Bearer <MCP_AUTH_TOKEN>"

6️⃣ Restart Hermes Agent

✅ Start using Sure tools:
   • get_accounts - View all accounts
   • get_transactions - Recent transactions
   • get_categories - Transaction categories
   • sync_accounts - Trigger account sync"""


@mcp.tool()
def check_auth_status() -> str:
    """Check if authentication is configured for Sure API."""
    try:
        api_url = os.getenv("SURE_API_URL")
        api_key = os.getenv("SURE_API_KEY")
        access_token = os.getenv("SURE_ACCESS_TOKEN")

        status = ""

        if api_url:
            status += f"✅ API URL: {api_url}\n"
        else:
            status += "❌ SURE_API_URL not configured\n"

        if api_key:
            status += "✅ API Key configured\n"
        elif access_token:
            status += "✅ Access Token configured\n"
        else:
            status += (
                "❌ No authentication configured (SURE_API_KEY or SURE_ACCESS_TOKEN)\n"
            )

        status += "\n💡 Try get_accounts to test the connection."

        return status
    except Exception as e:
        return f"Error checking auth status: {str(e)}"


@mcp.tool()
def check_connection() -> str:
    """Test connection to Sure API."""
    try:
        with get_client() as client:
            response = client.get("/api/v1/usage")
            data = handle_response(response)

            return (
                f"✅ Connected to Sure API\n{json.dumps(data, indent=2, default=str)}"
            )
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        return f"❌ Connection failed: {str(e)}"


@mcp.tool()
def get_accounts() -> str:
    """Get all financial accounts from Sure."""
    try:
        with get_client() as client:
            response = client.get("/api/v1/accounts")
            data = handle_response(response)

            # Handle paginated response
            accounts = data.get("accounts") or data.get("data") or data
            if isinstance(accounts, dict):
                accounts = accounts.get("accounts", [])

            account_count = len(accounts) if isinstance(accounts, list) else "unknown"
            logger.info("✅ Retrieved %s accounts", account_count)
            return json.dumps(accounts, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to get accounts: {e}")
        return f"Error getting accounts: {str(e)}"


@mcp.tool()
def get_transactions(
    limit: int = 25,
    start_date: str | None = None,
    end_date: str | None = None,
    account_ids: str | None = None,
    category_ids: str | None = None,
    search: str | None = None,
) -> str:
    """
    Get transactions from Sure.

    Args:
        limit: Number of transactions per page (default: 25, max: 100)
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        account_ids: Comma-separated account IDs to filter by
        category_ids: Comma-separated category IDs to filter by
        search: Search term to filter transactions
    """
    try:
        with get_client() as client:
            params: dict[str, Any] = {"per_page": min(limit, 100)}

            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date
            if account_ids:
                params["account_ids"] = account_ids
            if category_ids:
                params["category_ids"] = category_ids
            if search:
                params["search"] = search

            response = client.get("/api/v1/transactions", params=params)
            data = handle_response(response)

            # Handle paginated response
            transactions = data.get("transactions") or data.get("data") or data
            if isinstance(transactions, dict):
                transactions = transactions.get("transactions", [])

            transaction_count = (
                len(transactions) if isinstance(transactions, list) else "unknown"
            )
            logger.info("✅ Retrieved %s transactions", transaction_count)
            return json.dumps(transactions, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to get transactions: {e}")
        return f"Error getting transactions: {str(e)}"


@mcp.tool()
def get_transaction(transaction_id: str) -> str:
    """
    Get a single transaction by ID.

    Args:
        transaction_id: The ID of the transaction
    """
    try:
        with get_client() as client:
            response = client.get(f"/api/v1/transactions/{transaction_id}")
            data = handle_response(response)

            return json.dumps(data, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to get transaction: {e}")
        return f"Error getting transaction: {str(e)}"


@mcp.tool()
def create_transaction(
    account_id: str,
    amount: float,
    name: str,
    date: str,
    category_id: str | None = None,
    notes: str | None = None,
    nature: str | None = None,
) -> str:
    """
    Create a new transaction in Sure.

    Args:
        account_id: The account ID to add the transaction to
        amount: Transaction amount (use nature to specify income/expense)
        name: Transaction name/payee
        date: Transaction date in YYYY-MM-DD format
        category_id: Optional category ID
        notes: Optional notes
        nature: Optional "income" or "expense" to set amount sign
    """
    try:
        with get_client() as client:
            payload: dict[str, Any] = {
                "account_id": account_id,
                "amount": amount,
                "name": name,
                "date": date,
            }

            if category_id:
                payload["category_id"] = category_id
            if notes:
                payload["notes"] = notes
            if nature:
                payload["nature"] = nature

            response = client.post(
                "/api/v1/transactions", json={"transaction": payload}
            )
            data = handle_response(response)

            logger.info("✅ Created transaction")
            return json.dumps(data, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to create transaction: {e}")
        return f"Error creating transaction: {str(e)}"


@mcp.tool()
def update_transaction(
    transaction_id: str,
    amount: float | None = None,
    name: str | None = None,
    date: str | None = None,
    category_id: str | None = None,
    notes: str | None = None,
) -> str:
    """
    Update an existing transaction in Sure.

    Args:
        transaction_id: The ID of the transaction to update
        amount: New transaction amount
        name: New transaction name/payee
        date: New transaction date in YYYY-MM-DD format
        category_id: New category ID
        notes: New notes
    """
    try:
        with get_client() as client:
            payload: dict[str, Any] = {}

            if amount is not None:
                payload["amount"] = amount
            if name is not None:
                payload["name"] = name
            if date is not None:
                payload["date"] = date
            if category_id is not None:
                payload["category_id"] = category_id
            if notes is not None:
                payload["notes"] = notes

            response = client.patch(
                f"/api/v1/transactions/{transaction_id}", json={"transaction": payload}
            )
            data = handle_response(response)

            logger.info(f"✅ Updated transaction {transaction_id}")
            return json.dumps(data, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to update transaction: {e}")
        return f"Error updating transaction: {str(e)}"


@mcp.tool()
def delete_transaction(transaction_id: str) -> str:
    """
    Delete a transaction from Sure.

    Args:
        transaction_id: The ID of the transaction to delete
    """
    try:
        with get_client() as client:
            response = client.delete(f"/api/v1/transactions/{transaction_id}")
            data = handle_response(response)

            logger.info(f"✅ Deleted transaction {transaction_id}")
            return json.dumps(data, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to delete transaction: {e}")
        return f"Error deleting transaction: {str(e)}"


@mcp.tool()
def get_categories() -> str:
    """Get all transaction categories from Sure."""
    try:
        with get_client() as client:
            response = client.get("/api/v1/categories")
            data = handle_response(response)

            # Handle paginated response
            categories = data.get("categories") or data.get("data") or data
            if isinstance(categories, dict):
                categories = categories.get("categories", [])

            category_count = (
                len(categories) if isinstance(categories, list) else "unknown"
            )
            logger.info("✅ Retrieved %s categories", category_count)
            return json.dumps(categories, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to get categories: {e}")
        return f"Error getting categories: {str(e)}"


@mcp.tool()
def get_category(category_id: str) -> str:
    """
    Get a single category by ID.

    Args:
        category_id: The ID of the category
    """
    try:
        with get_client() as client:
            response = client.get(f"/api/v1/categories/{category_id}")
            data = handle_response(response)

            return json.dumps(data, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to get category: {e}")
        return f"Error getting category: {str(e)}"


@mcp.tool()
def sync_accounts() -> str:
    """Trigger account sync to refresh data from financial institutions."""
    try:
        with get_client() as client:
            response = client.post("/api/v1/sync")
            data = handle_response(response)

            logger.info("✅ Triggered account sync")
            return json.dumps(data, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to sync accounts: {e}")
        return f"Error syncing accounts: {str(e)}"


@mcp.tool()
def get_usage() -> str:
    """Get API usage and rate limit information."""
    try:
        with get_client() as client:
            response = client.get("/api/v1/usage")
            data = handle_response(response)

            return json.dumps(data, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to get usage: {e}")
        return f"Error getting usage: {str(e)}"


@mcp.tool()
def list_chats() -> str:
    """Get all AI chat sessions from Sure."""
    try:
        with get_client() as client:
            response = client.get("/api/v1/chats")
            data = handle_response(response)

            # Handle paginated response
            chats = data.get("chats") or data.get("data") or data
            if isinstance(chats, dict):
                chats = chats.get("chats", [])

            chat_count = len(chats) if isinstance(chats, list) else "unknown"
            logger.info("✅ Retrieved %s chats", chat_count)
            return json.dumps(chats, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to list chats: {e}")
        return f"Error listing chats: {str(e)}"


@mcp.tool()
def create_chat(title: str | None = None) -> str:
    """
    Create a new AI chat session in Sure.

    Args:
        title: Optional title for the chat
    """
    try:
        with get_client() as client:
            payload: dict[str, Any] = {}
            if title:
                payload["title"] = title

            response = client.post("/api/v1/chats", json=payload)
            data = handle_response(response)

            logger.info("✅ Created new chat")
            return json.dumps(data, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to create chat: {e}")
        return f"Error creating chat: {str(e)}"


@mcp.tool()
def get_chat(chat_id: str) -> str:
    """
    Get a chat session by ID.

    Args:
        chat_id: The ID of the chat
    """
    try:
        with get_client() as client:
            response = client.get(f"/api/v1/chats/{chat_id}")
            data = handle_response(response)

            return json.dumps(data, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to get chat: {e}")
        return f"Error getting chat: {str(e)}"


@mcp.tool()
def send_message(chat_id: str, content: str) -> str:
    """
    Send a message to Sure's AI assistant.

    Args:
        chat_id: The ID of the chat
        content: The message content
    """
    try:
        with get_client() as client:
            response = client.post(
                f"/api/v1/chats/{chat_id}/messages", json={"content": content}
            )
            data = handle_response(response)

            logger.info("✅ Sent message")
            return json.dumps(data, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        return f"Error sending message: {str(e)}"


@mcp.tool()
def delete_chat(chat_id: str) -> str:
    """
    Delete a chat session.

    Args:
        chat_id: The ID of the chat to delete
    """
    try:
        with get_client() as client:
            response = client.delete(f"/api/v1/chats/{chat_id}")
            data = handle_response(response)

            logger.info(f"✅ Deleted chat {chat_id}")
            return json.dumps(data, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to delete chat: {e}")
        return f"Error deleting chat: {str(e)}"


def main() -> None:
    """Main entry point for the server."""
    logger.info("Starting Sure MCP Server...")
    try:
        logger.info("MCP endpoint: http://%s:%s%s", mcp.settings.host, PORT, MCP_PATH)
        import uvicorn

        uvicorn.run(
            app,
            host=mcp.settings.host,
            port=PORT,
            log_level=mcp.settings.log_level.lower(),
        )
    except Exception as e:
        logger.error(f"Failed to run server: {str(e)}")
        raise


# ASGI application for uvicorn/gunicorn and in-process tests. When
# MCP_AUTH_TOKEN is set, Hermes must send `Authorization: Bearer <token>`.
app: ASGIApp = BearerAuthMiddleware(
    mcp.streamable_http_app(),
    path=MCP_PATH,
    token=os.getenv("MCP_AUTH_TOKEN"),
)

if __name__ == "__main__":
    main()
