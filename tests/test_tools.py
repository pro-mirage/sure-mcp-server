"""Tests for the request payloads that tools send to the Sure API."""

import importlib
import json

import httpx


def load_server(monkeypatch, handler):
    """Load the server with a mocked Sure API that records requests."""
    monkeypatch.setenv("SURE_API_URL", "https://sure.example.com")
    monkeypatch.setenv("SURE_API_KEY", "test-key")
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)

    import sure_mcp_server.server as server

    server = importlib.reload(server)
    transport = httpx.MockTransport(handler)

    def fake_client() -> httpx.Client:
        return httpx.Client(
            base_url=server.get_api_url(),
            headers=server.get_auth_header(),
            transport=transport,
        )

    monkeypatch.setattr(server, "get_client", fake_client)
    return server


def recorder():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"id": "abc"})

    return calls, handler


def test_create_transaction_sends_currency(monkeypatch):
    calls, handler = recorder()
    server = load_server(monkeypatch, handler)

    server.create_transaction(
        account_id="acc", amount=34.2477, name="Deposit", date="2026-11-14",
        nature="income", currency="usdt",
    )

    body = json.loads(calls[0].content)["transaction"]
    assert calls[0].url.path == "/api/v1/transactions"
    assert body["currency"] == "USDT"
    assert body["nature"] == "income"


def test_create_transaction_omits_currency_by_default(monkeypatch):
    calls, handler = recorder()
    server = load_server(monkeypatch, handler)

    server.create_transaction(account_id="acc", amount=1, name="x", date="2026-11-14")

    assert "currency" not in json.loads(calls[0].content)["transaction"]


def test_update_transaction_sends_currency_and_nature(monkeypatch):
    calls, handler = recorder()
    server = load_server(monkeypatch, handler)

    server.update_transaction("tx1", amount=5, currency="usd", nature="expense")

    body = json.loads(calls[0].content)["transaction"]
    assert calls[0].method == "PATCH"
    assert body == {"amount": 5, "currency": "USD", "nature": "expense"}


def test_create_trade_buy(monkeypatch):
    calls, handler = recorder()
    server = load_server(monkeypatch, handler)

    server.create_trade(
        account_id="acc", type="Buy", date="2026-11-14",
        ticker="AAPL", qty=0.041179, price=355.75, fee=0.35,
    )

    body = json.loads(calls[0].content)["trade"]
    assert calls[0].url.path == "/api/v1/trades"
    assert body == {
        "account_id": "acc", "type": "buy", "date": "2026-11-14",
        "ticker": "AAPL", "qty": 0.041179, "price": 355.75, "fee": 0.35,
    }


def test_create_trade_linked_deposit(monkeypatch):
    calls, handler = recorder()
    server = load_server(monkeypatch, handler)

    server.create_trade(
        account_id="acc", type="deposit", date="2026-11-14",
        amount=10000, transfer_account_id="bank",
    )

    body = json.loads(calls[0].content)["trade"]
    assert body["transfer_account_id"] == "bank"
    assert body["amount"] == 10000


def test_create_trade_rejects_unknown_type(monkeypatch):
    calls, handler = recorder()
    server = load_server(monkeypatch, handler)

    result = server.create_trade(account_id="acc", type="short", date="2026-11-14")

    assert result.startswith("Error creating trade")
    assert calls == []


def test_get_holdings_filters(monkeypatch):
    calls: list[httpx.Request] = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"holdings": [{"id": "h1"}]})

    server = load_server(monkeypatch, handler)
    result = json.loads(server.get_holdings(account_id="acc", limit=500))

    assert result == [{"id": "h1"}]
    assert calls[0].url.params["account_id"] == "acc"
    assert calls[0].url.params["per_page"] == "100"


def test_trade_update_and_delete_paths(monkeypatch):
    calls, handler = recorder()
    server = load_server(monkeypatch, handler)

    server.update_trade("t1", qty=1, price=2)
    server.delete_trade("t1")

    assert calls[0].method == "PATCH"
    assert json.loads(calls[0].content) == {"trade": {"qty": 1, "price": 2}}
    assert calls[1].method == "DELETE"
    assert calls[1].url.path == "/api/v1/trades/t1"
