# DealProof Settle

A small demo: tamper-evident deal files that are settled as ETH payments from a Tangem hardware wallet, driven by Claude Code and the Tangem MCP server.

## What it does

1. A deal (here: an agreed job offer, `deals/offer-001.json`) holds its `terms` plus a `deal_hash`.
2. `verify_deal.py` recomputes the hash and prints `OK` or `TAMPERED`.
3. If the deal is `OK`, the `settle` workflow (see `CLAUDE.md`) creates a payment request in the Tangem app for the settlement amount in the terms. The user approves and signs it on their card, so no keys ever touch this repo or the agent.
4. The result (`deal_hash`, `intentId`, deeplink, timestamp, `txHash`) is recorded in `settlements.json` and the deal is marked `settled`.

## Flow: `settle <deal file>`

```
verify_deal.py ──TAMPERED──▶ stop (no Tangem call, no intent)
      │ OK
      ▼
already settled? ──yes──▶ stop (no duplicate intent)
      │ no
      ▼
POST <ATTEST_URL>/attest + check_attestation.py ──FAILED──▶ stop (no intent)
      │ OK → deal.attestation = {url, quote_prefix, quote_sha256, attested_at}
      ▼
wallets__get_tokens ─▶ transactions__send_transaction (sendNotification: true)
      │
      ▼
settlements.json += {deal_hash, intentId, deeplink, timestamp}; deal → settlement_pending
      │  user signs in the Tangem app
      ▼
transactions__get_transaction_status ─COMPLETED─▶ record txHash; deal → settled
```

## TEE attestation (attest-service)

`attest-service/docker-compose.yml` runs on Phala Cloud (Intel TDX via dstack). You can paste it straight into the dashboard: it uses the stock `python:3.12-slim` image, installs `fastapi`, `uvicorn` and `dstack-sdk`, writes the app with a heredoc and starts uvicorn on port 8000.

- `GET /health` returns `ok`.
- `POST /attest {"deal_hash": "<64 hex>"}` calls `DstackClient().get_quote(bytes.fromhex(deal_hash))` through `/var/run/dstack.sock` and returns the TDX quote. The quote's `report_data` contains the deal hash.

`check_attestation.py` confirms that the returned quote's report_data matches the deal's `deal_hash`. It doesn't verify Intel's signature chain; use a DCAP verifier for that. `offer-001` was settled before attestation existed, so it has no attestation record.

## Demo result

`offer-001` settled with a 0.001 ETH deposit on Ethereum mainnet:
https://etherscan.io/tx/0x98ac14ff362b4dc4fec30552cfe4b0b2d1eaac882eea9491ae99855495c4de46

## How the tamper check works

`deal_hash` is the SHA-256 of the canonical JSON of `terms` (keys sorted, no whitespace, UTF-8). `deal_hash` itself sits outside `terms`, so it isn't part of the hashed data.

Every term, including the settlement amount and recipient address, is inside `terms`. If a field changes, even by one character, the hash no longer matches, so you can't quietly swap the payee or the amount. For example, raising the salary by 5000 without updating the hash makes `verify_deal.py` print `TAMPERED`, and `settle` refuses to create a payment request.

```
python verify_deal.py deals/offer-001.json   # OK
```

The deal file's `status` field is outside `terms`, so it can change from `agreed` to `settled` without breaking the hash.
