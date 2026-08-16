from __future__ import annotations

import os
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .infrai_storage import InfraiError, InfraiStorage
from .order_updates import OrderLedger, OrderUpdateService


class CheckoutRequest(BaseModel):
    order_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)


class FulfillmentRequest(BaseModel):
    receipt_key: str = Field(min_length=1)


class OrderResponse(BaseModel):
    order_id: str
    customer_id: str
    state: str
    receipt_key: str | None


class CustomerUpdateResponse(BaseModel):
    order_id: str
    status: str
    receipt_download_url: str | None
    expires_seconds: int | None


app = FastAPI(title="Private order receipt service")
ledger = OrderLedger()


def _updates() -> OrderUpdateService:
    bucket = os.environ.get("RECEIPT_BUCKET", "private-order-receipts")
    return OrderUpdateService(ledger, InfraiStorage(), bucket)


@app.post("/checkouts", response_model=OrderResponse, status_code=201)
def checkout(request: CheckoutRequest) -> dict[str, object]:
    return asdict(ledger.checkout(request.order_id, request.customer_id))


@app.post("/orders/{order_id}/fulfillment", response_model=OrderResponse)
def fulfill(order_id: str, request: FulfillmentRequest) -> dict[str, object]:
    try:
        return asdict(ledger.fulfill(order_id, request.receipt_key))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="order not found") from exc


@app.get("/orders/{order_id}/customer-update", response_model=CustomerUpdateResponse)
def customer_update(order_id: str) -> dict[str, object]:
    try:
        return asdict(_updates().customer_update(order_id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="order not found") from exc
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)}) from exc
