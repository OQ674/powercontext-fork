"""订单查询 HTTP 接口的既有行为回归测试（SPEC-API-001）。"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from order_fulfillment.repository import InMemoryOrderRepository, load_orders_from_csv
from order_fulfillment.service import create_server

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "orders.csv"


@pytest.fixture()
def server_url():
    repository = InMemoryOrderRepository(load_orders_from_csv(DATA_FILE))
    server = create_server(repository, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[0], server.server_address[1]
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _get(url: str):
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def test_orders_endpoint_returns_every_order(server_url):
    status, payload = _get(f"{server_url}/orders")
    assert status == 200
    assert payload["total"] == 8
    assert len(payload["orders"]) == 8


def test_orders_endpoint_supports_status_filter(server_url):
    status, payload = _get(f"{server_url}/orders?status=pending")
    assert status == 200
    assert payload["total"] == 3
    assert {order["status"] for order in payload["orders"]} == {"pending"}


def test_orders_endpoint_supports_sort_and_limit(server_url):
    status, payload = _get(f"{server_url}/orders?sort_by=amount&limit=2")
    assert status == 200
    amounts = [order["amount"] for order in payload["orders"]]
    assert amounts == sorted(amounts)
    assert len(amounts) == 2


def test_amount_is_rendered_with_two_decimals(server_url):
    _, payload = _get(f"{server_url}/orders")
    assert all(len(order["amount"].split(".")[1]) == 2 for order in payload["orders"])


def test_unknown_path_returns_404(server_url):
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(f"{server_url}/nope", timeout=10)
    assert excinfo.value.code == 404
