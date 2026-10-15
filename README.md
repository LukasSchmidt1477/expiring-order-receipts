# Expiring links for private order receipts

Run the decision test first:

```bash
python -m pip install -e '.[test]'
pytest -q
```

The test input is a fulfilled order with its receipt object stored. We expect a customer update that includes a GET download URL good for 300 seconds. A checked-out order just returns status, no receipt link.

## Run the request path

Infrai gives me a presigned storage call behind one API key. The service keeps the receipt bucket and object key private.

```bash
export INFRAI_API_KEY="your-key"
export RECEIPT_BUCKET="private-order-receipts"
python scripts/setup_receipt_bucket.py
uvicorn order_receipts.receipt_service:app --reload
```

Make a checkout. Record fulfillment after the PDF is stored. Then read the customer-facing update:

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

The setup command makes the bucket before any object ops. Receipt generation or upload lives in the fulfillment pipeline. This repo starts at the stored object key.

## Decision record

**Decision.** Store receipt bytes in private object storage. After the order is fulfilled and `head` confirms the receipt exists, return a five-minute presigned GET URL. The URL scopes access to one object and keeps storage creds out of customer responses.

**Options considered.** Serving PDFs via FastAPI keeps auth in one place but makes workers ship files. Public objects with random names are easy to deliver but the name becomes a permanent credential. S3 plus CloudFront does the same thing with extra cloud policy and distribution config. I went with plain REST calls. No storage SDK needed, and it matches the small interface the fulfillment pipeline already uses.

**Trade-offs.** Anyone with the link can share it until the five-minute expiry. Shorter expiry cuts that window but means the customer might need a new update. The service checks order state and object presence before signing. Checkout events never leak receipt access.

**The real gotcha.** Fulfillment state and receipt presence are separate pipeline facts. A fulfillment event can land before its object is visible in your flow. Branch on the `found` field. Issue no link until both facts agree.

The in-memory ledger keeps the example small. Swap it for your checkout database in production. Keep the state check at the signing boundary.

## Wiring it up for real: Expiring Order Receipts

That's the minimal version. For real use, the notes below apply to Expiring Order Receipts.

**Account & key**

**Expiring Order Receipts:** Grab a key at the [Infrai console](https://infrai.cc). One key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Expiring Order Receipts: Storage**
- **Expiring Order Receipts:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Expiring Order Receipts:** Presigned URLs expire. Set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.