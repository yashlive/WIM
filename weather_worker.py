"""
WIM background weather ingester.

Run this on a schedule (recommended: every 30 minutes). It calls the weather
provider/fusion layer in weather_backend.py, then:
  1) upserts one current snapshot per mine into weather_latest; and
  2) appends immutable fused/provider snapshots into history tables.

The Streamlit app does not call weather providers anymore.
"""
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone

import requests

import weather_backend as wb

UTC = timezone.utc
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()


def _headers(extra=None):
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _require_config():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _serializable(value):
    return json.loads(json.dumps(value, default=_json_default))


def _serialize_by_day(by_day):
    out = {}
    for day, rows in by_day.items():
        key = day.isoformat() if hasattr(day, "isoformat") else str(day)
        out[key] = [
            {"time": dt.isoformat(), "data": _serializable(data)}
            for dt, data in rows
        ]
    return out


def _hash_payload(payload):
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _post(table, body, prefer="return=minimal", params=None):
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=_headers({"Prefer": prefer}),
        params=params or {},
        json=body,
        timeout=20,
    )
    if not r.ok:
        raise RuntimeError(f"Supabase {table} write failed: HTTP {r.status_code}: {r.text[:500]}")
    return r


def upsert_latest(site, run_id, fetched_at, payload):
    body = {
        "site_id": site["id"],
        "site_name": site["name"],
        "lat": float(site["lat"]),
        "lon": float(site["lon"]),
        "run_id": run_id,
        "fetched_at": fetched_at,
        "forecast_payload": payload,
    }
    _post(
        "weather_latest",
        body,
        prefer="resolution=merge-duplicates,return=minimal",
        params={"on_conflict": "site_id"},
    )


def append_fused_history(site, run_id, fetched_at, payload):
    payload_hash = _hash_payload(payload)
    body = {
        "run_id": run_id,
        "site_id": site["id"],
        "site_name": site["name"],
        "lat": float(site["lat"]),
        "lon": float(site["lon"]),
        "fetched_at": fetched_at,
        "payload_hash": payload_hash,
        "forecast_payload": payload,
    }
    # Append every scheduled fused snapshot. Nothing in this table is updated.
    _post("forecast_history", body, prefer="return=minimal")


def append_provider_history(site, run_id, fetched_at, provider_payloads):
    rows = []
    for provider, payload in (provider_payloads or {}).items():
        if payload is None:
            continue
        safe_payload = _serializable(payload)
        payload_hash = _hash_payload(safe_payload)
        rows.append({
            "run_id": run_id,
            "site_id": site["id"],
            "site_name": site["name"],
            "provider": provider,
            "lat": float(site["lat"]),
            "lon": float(site["lon"]),
            "fetched_at": fetched_at,
            "payload_hash": payload_hash,
            "provider_payload": safe_payload,
        })
    if not rows:
        return
    _post(
        "provider_forecast_history",
        rows,
        prefer="resolution=ignore-duplicates,return=minimal",
        params={"on_conflict": "site_id,provider,payload_hash"},
    )


def ingest_site(site, run_id):
    fetched_at = datetime.now(UTC).isoformat()
    by_day, mc_data, source_status, imd_advisory = wb.build_forecast(
        site["lat"],
        site["lon"],
        days=7,
        imd_subdivision=site.get("imd_subdivision", ""),
    )

    payload = {
        "schema_version": 1,
        "site": {
            "id": site["id"],
            "name": site["name"],
            "lat": float(site["lat"]),
            "lon": float(site["lon"]),
            "type": site.get("type", ""),
            "imd_subdivision": site.get("imd_subdivision", ""),
        },
        "by_day": _serialize_by_day(by_day),
        "mc_data": _serializable(mc_data),
        "source_status": _serializable(source_status),
        "imd_advisory": _serializable(imd_advisory),
        "generated_at": fetched_at,
    }

    # Current dashboard state (mutable/current).
    upsert_latest(site, run_id, fetched_at, payload)

    # Immutable history for future provider scoring/backtesting.
    append_fused_history(site, run_id, fetched_at, payload)
    append_provider_history(site, run_id, fetched_at, wb.LAST_PROVIDER_PAYLOADS)

    online = [k for k, v in source_status.items() if str(v).startswith("ok")]
    print(f"✓ {site['name']}: saved current + history; online={', '.join(online) or 'none'}")


def main():
    _require_config()
    run_id = str(uuid.uuid4())
    failures = []
    print(f"WIM ingestion run {run_id} — {datetime.now(UTC).isoformat()}")
    for site in wb.DEFAULT_SITES:
        try:
            ingest_site(site, run_id)
        except Exception as exc:
            failures.append((site["name"], str(exc)))
            print(f"✗ {site['name']}: {exc}", file=sys.stderr)

    if failures:
        print("\nFailures:", file=sys.stderr)
        for name, err in failures:
            print(f"- {name}: {err}", file=sys.stderr)
        # Non-zero exit lets the scheduler alert on partial ingestion failures.
        raise SystemExit(1)

    print("All mine forecasts ingested successfully.")


if __name__ == "__main__":
    main()
