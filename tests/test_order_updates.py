from order_receipts.order_updates import OrderLedger, OrderUpdateService


class ReceiptStorageStub:
    def __init__(self, found: bool) -> None:
        self.found = found
        self.presign_calls = 0

    def head_object(self, bucket: str, key: str) -> dict[str, object]:
        return {"found": self.found}

    def presign_download(self, bucket: str, key: str, order_id: str) -> dict[str, object]:
        self.presign_calls += 1
        return {"url": "https://download.example/signed-receipt"}


def test_fulfilled_order_with_stored_receipt_gets_expiring_link() -> None:
    ledger = OrderLedger()
    ledger.checkout("ord-1042", "cus-88")
    ledger.fulfill("ord-1042", "receipts/ord-1042.pdf")
    storage = ReceiptStorageStub(found=True)

    update = OrderUpdateService(ledger, storage, "receipts").customer_update("ord-1042")

    assert update.status == "fulfilled"
    assert update.receipt_download_url == "https://download.example/signed-receipt"
    assert update.expires_seconds == 300
    assert storage.presign_calls == 1


def test_checkout_does_not_expose_a_receipt_link() -> None:
    ledger = OrderLedger()
    ledger.checkout("ord-1043", "cus-89")
    storage = ReceiptStorageStub(found=True)

    update = OrderUpdateService(ledger, storage, "receipts").customer_update("ord-1043")

    assert update.status == "checked_out"
    assert update.receipt_download_url is None
    assert storage.presign_calls == 0
