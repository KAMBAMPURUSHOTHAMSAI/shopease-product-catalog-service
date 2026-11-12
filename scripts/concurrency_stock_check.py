"""Exercise MySQL row-locking with two simultaneous stock-out requests.

Prepare a product with exactly 10 units of stock, then run:
  $env:ADMIN_ACCESS_TOKEN = "<admin access token>"
  python scripts/concurrency_stock_test.py --product-id 1 --quantity 7
Expected: one HTTP 200 and one HTTP 409; final stock is 3.
Run this against the Docker/MySQL service, not SQLite.
"""
import argparse
import os
from concurrent.futures import ThreadPoolExecutor
import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="http://localhost:8005")
parser.add_argument("--product-id", type=int, required=True)
parser.add_argument("--quantity", type=int, default=7)
args = parser.parse_args()
token = os.getenv("ADMIN_ACCESS_TOKEN")
if not token:
    raise SystemExit("Set ADMIN_ACCESS_TOKEN in this PowerShell session; do not put it in a file.")
headers = {"Authorization": f"Bearer {token}"}
url = f"{args.base_url.rstrip('/')}/api/inventory/{args.product_id}/stock-out"

def send_one(_):
    response = httpx.post(url, json={"quantity": args.quantity, "remarks": "Concurrent stock consistency test"}, headers=headers, timeout=30)
    return response.status_code, response.text

with ThreadPoolExecutor(max_workers=2) as pool:
    results = list(pool.map(send_one, range(2)))
for status, body in results:
    print(f"HTTP {status}: {body[:240]}")
counts = [status for status, _ in results]
if counts.count(200) != 1 or counts.count(409) != 1:
    raise SystemExit("Unexpected result. For this check, start with 10 stock and request 7 units twice.")
stock_response = httpx.get(f"{args.base_url.rstrip('/')}/api/inventory/{args.product_id}", headers=headers, timeout=30)
stock_response.raise_for_status()
final_stock = stock_response.json()["stock_quantity"]
if final_stock != 10 - args.quantity:
    raise SystemExit(f"Unexpected final stock: {final_stock}; expected {10 - args.quantity}.")
print(f"PASS: one request succeeded, one was rejected, and final stock is {final_stock}.")
