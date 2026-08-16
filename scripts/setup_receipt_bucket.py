import os

from order_receipts.infrai_storage import InfraiStorage


def main() -> None:
    bucket = os.environ.get("RECEIPT_BUCKET", "private-order-receipts")
    InfraiStorage().create_bucket(bucket)
    print(f"Receipt bucket ready: {bucket}")


if __name__ == "__main__":
    main()
