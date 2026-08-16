from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Protocol


class OrderState(StrEnum):
    CHECKED_OUT = "checked_out"
    FULFILLED = "fulfilled"


@dataclass(frozen=True)
class Order:
    order_id: str
    customer_id: str
    state: OrderState
    receipt_key: str | None = None


@dataclass(frozen=True)
class CustomerUpdate:
    order_id: str
    status: OrderState
    receipt_download_url: str | None
    expires_seconds: int | None


class ReceiptStorage(Protocol):
    def head_object(self, bucket: str, key: str) -> dict[str, object]: ...

    def presign_download(self, bucket: str, key: str, order_id: str) -> dict[str, object]: ...


class OrderLedger:
    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}

    def checkout(self, order_id: str, customer_id: str) -> Order:
        order = Order(order_id, customer_id, OrderState.CHECKED_OUT)
        self._orders[order_id] = order
        return order

    def fulfill(self, order_id: str, receipt_key: str) -> Order:
        order = replace(self.get(order_id), state=OrderState.FULFILLED, receipt_key=receipt_key)
        self._orders[order_id] = order
        return order

    def get(self, order_id: str) -> Order:
        try:
            return self._orders[order_id]
        except KeyError as exc:
            raise LookupError(order_id) from exc


class OrderUpdateService:
    def __init__(self, ledger: OrderLedger, storage: ReceiptStorage, bucket: str) -> None:
        self._ledger = ledger
        self._storage = storage
        self._bucket = bucket

    def customer_update(self, order_id: str) -> CustomerUpdate:
        order = self._ledger.get(order_id)
        if order.state != OrderState.FULFILLED or order.receipt_key is None:
            return CustomerUpdate(order.order_id, order.state, None, None)

        object_state = self._storage.head_object(self._bucket, order.receipt_key)
        if not object_state.get("found"):
            return CustomerUpdate(order.order_id, order.state, None, None)

        signed = self._storage.presign_download(self._bucket, order.receipt_key, order.order_id)
        return CustomerUpdate(order.order_id, order.state, str(signed["url"]), 300)
