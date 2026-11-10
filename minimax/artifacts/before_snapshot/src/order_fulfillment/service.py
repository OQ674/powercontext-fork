"""订单查询 HTTP 服务（SPEC-API-001）。

使用标准库 ``http.server`` 暴露 ``GET /orders``，便于在没有额外依赖的环境运行演示。
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .filters import filter_orders
from .models import Order
from .repository import OrderRepository


class OrderQueryHandler(BaseHTTPRequestHandler):
    """处理 ``GET /orders`` 请求。"""

    repository: OrderRepository = None  # type: ignore[assignment]
    server_version = "OrderFulfillment/1.0"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler 约定
        parsed = urlparse(self.path)
        if parsed.path != "/orders":
            self._send_json(404, {"error": "not found"})
            return

        query = parse_qs(parsed.query)
        try:
            status = query.get("status", [None])[0]
            min_amount = query.get("min_amount", [None])[0]
            max_amount = query.get("max_amount", [None])[0]
            sort_by = query.get("sort_by", ["created_at"])[0]
            offset = query.get("offset", [None])[0]
            limit = query.get("limit", [None])[0]
            orders = filter_orders(
                self.repository.all(),
                status=status,
                sort_by=sort_by,
                offset=int(offset) if offset is not None else None,
                limit=int(limit) if limit is not None else None,
            )
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
            return

        self._send_json(200, {"orders": [order.to_dict() for order in orders], "total": len(orders)})

    def log_message(self, fmt: str, *args) -> None:  # pragma: no cover - 静默访问日志
        return

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(repository: OrderRepository, host: str = "127.0.0.1", port: int = 8080) -> ThreadingHTTPServer:
    """创建订单查询服务实例。"""

    handler = type("BoundOrderQueryHandler", (OrderQueryHandler,), {"repository": repository})
    return ThreadingHTTPServer((host, port), handler)


__all__ = ["OrderQueryHandler", "create_server", "Decimal", "InvalidOperation", "Order"]
