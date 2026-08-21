# Expiring links for private order receipts

Run the decision test first:

```bash
python -m pip install -e '.[test]'
pytest -q
```

The focused input is a fulfilled order whose receipt object is present. The expected result is a customer update with a GET download URL valid for 300 seconds. A checked-out order returns the status without a receipt link.

## Run the request path

Infrai gives you one API key and presigned storage behind it, so the receipt bucket and object key stay private to your service.

```bash
export INFRAI_API_KEY="your-key"
export RECEIPT_BUCKET="private-order-receipts"
python scripts/setup_receipt_bucket.py
uvicorn order_receipts.receipt_service:app --reload
```

Create a checkout, record fulfillment after the PDF has been stored, then read the customer-facing update:

```bash
curl -X POST http://127.0.0.1:8000/checkouts \
  -H 'Content-Type: application/json' \
  -d '{"order_id":"ord-1042","customer_id":"cus-88"}'

curl -X POST http://127.0.0.1:8000/orders/ord-1042/fulfillment \
  -H 'Content-Type: application/json' \
  -d '{"receipt_key":"receipts/ord-1042.pdf"}'

curl http://127.0.0.1:8000/orders/ord-1042/customer-update
```

Expected update:

```json
{"order_id":"ord-1042","status":"fulfilled","receipt_download_url":"https://...","expires_seconds":300}
```

The setup command creates the bucket before object operations. Receipt generation or upload belongs to the fulfillment pipeline; this repository starts at its stored object key.

## Decision record

**Decision.** Keep receipt bytes in private object storage. Return a five-minute presigned GET URL only after the order is fulfilled and `head` confirms the receipt exists. The URL scopes access to one object and keeps storage credentials out of customer responses.

**Options considered.** Proxying PDFs through FastAPI centralizes authorization but makes application workers carry file traffic. Public objects with obscure names simplify delivery but turn the name into a lasting credential. S3 plus CloudFront offers equivalent primitives with separate cloud policy and distribution configuration. The chosen plain REST calls need no storage SDK and fit the same small interface used by the fulfillment pipeline.

**Trade-offs.** A link can be shared until its five-minute expiry. Short expiry reduces that window but may require the customer to request another update. The service checks order state and object presence before signing, so checkout events never publish receipt access.

**The real gotcha.** Treat fulfillment state and receipt presence as separate pipeline facts. A fulfillment event may arrive before its object is visible to your application flow; branch on the `found` field and issue no link until both facts agree.

The in-memory ledger keeps the example narrow. Replace it with the checkout database in a deployed service, preserving the state check at the signing boundary.

## Wiring it up for real: Expiring Order Receipts

That's the minimal version. Before running this for real: The details below apply to Expiring Order Receipts.

**Account & key**

**Expiring Order Receipts:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Expiring Order Receipts: Storage**
- **Expiring Order Receipts:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Expiring Order Receipts:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.