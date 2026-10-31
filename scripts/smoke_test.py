"""End-to-end smoke test against a running API (local or AWS). Produces validation evidence.

Usage:
    python scripts/smoke_test.py --base-url http://<elastic-ip> --api-key <key>
    python scripts/smoke_test.py --base-url http://127.0.0.1:8000 --api-key local-dev-key
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--api-key", required=True)
    ap.add_argument("--out", default="evidence")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    auth = {"X-API-Key": args.api_key}
    run = str(int(time.time()))
    results: list[dict] = []

    def check(name: str, resp: requests.Response, expected: int) -> requests.Response:
        ok = resp.status_code == expected
        results.append(
            {
                "check": name,
                "expected": expected,
                "actual": resp.status_code,
                "ms": round(resp.elapsed.total_seconds() * 1000, 1),
                "result": "PASS" if ok else "FAIL",
            }
        )
        return resp

    s = requests.Session()
    check("liveness", s.get(f"{base}/health", timeout=10), 200)
    check("readiness (DB reachable)", s.get(f"{base}/health/ready", timeout=10), 200)
    check("write without API key rejected", s.post(f"{base}/products", json={}, timeout=10), 401)
    check(
        "invalid product rejected",
        s.post(f"{base}/products", json={"sku": "x", "name": "", "price_cents": -1}, headers=auth, timeout=10),
        422,
    )
    shirt = check(
        "create product A",
        s.post(f"{base}/products", json={"sku": f"SMOKE-A-{run}", "name": "Smoke shirt", "price_cents": 49900, "stock": 5}, headers=auth, timeout=10),
        201,
    ).json()
    cap = check(
        "create product B",
        s.post(f"{base}/products", json={"sku": f"SMOKE-B-{run}", "name": "Smoke cap", "price_cents": 19900, "stock": 1}, headers=auth, timeout=10),
        201,
    ).json()
    check(
        "duplicate SKU rejected",
        s.post(f"{base}/products", json={"sku": f"SMOKE-A-{run}", "name": "dup", "price_cents": 1}, headers=auth, timeout=10),
        409,
    )
    order = check(
        "place order",
        s.post(
            f"{base}/orders",
            json={"customer_email": "smoke@example.com", "items": [{"product_id": shirt["id"], "quantity": 2}, {"product_id": cap["id"], "quantity": 1}]},
            headers=auth,
            timeout=10,
        ),
        201,
    ).json()
    check(
        "oversell rejected",
        s.post(f"{base}/orders", json={"customer_email": "smoke@example.com", "items": [{"product_id": cap["id"], "quantity": 1}]}, headers=auth, timeout=10),
        409,
    )
    check("read order back", s.get(f"{base}/orders/{order.get('id', 0)}", timeout=10), 200)
    stock = s.get(f"{base}/products/{shirt.get('id', 0)}", timeout=10).json().get("stock")
    results.append({"check": "stock decremented 5 -> 3", "expected": 3, "actual": stock, "ms": 0, "result": "PASS" if stock == 3 else "FAIL"})
    check("low-stock report", s.get(f"{base}/products", params={"low_stock": "true"}, timeout=10), 200)
    check("unknown route 404", s.get(f"{base}/does-not-exist", timeout=10), 404)

    width = max(len(r["check"]) for r in results)
    for r in results:
        print(f"{r['result']:4}  {r['check']:<{width}}  expected={r['expected']!s:<4} actual={r['actual']!s:<4} {r['ms']} ms")
    failed = sum(r["result"] == "FAIL" for r in results)
    print(f"\n{len(results) - failed}/{len(results)} checks passed")

    out = Path(args.out)
    out.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = out / f"smoke-{stamp}.json"
    report.write_text(json.dumps({"base_url": base, "run_at": stamp, "results": results}, indent=2))
    print(f"evidence written to {report}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
