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
- `POST /attest {"deal_hash": "<64 hex>"}` calls `DstackClient().get_quote(bytes.fromhex(deal_hash) + b"\x00" * 32)` (exactly 64 bytes) through `/var/run/dstack.sock` and returns the TDX quote. The quote's `report_data` contains the deal hash.

`check_attestation.py` confirms that the returned quote's report_data matches the deal's `deal_hash`. It doesn't verify Intel's signature chain; see [How to verify a quote](#how-to-verify-a-quote).

The full `/attest` responses (`deal_hash`, `quote`, `event_log`) are kept in `attestations/`. `offer-001` was attested after it had already settled, so its deal file has no `attestation` field. `offer-002` was attested before its payment request was created.

## How to verify a quote

Anyone can check that the quotes in `attestations/` are genuine Intel TDX quotes that commit to the deal hashes. There are three levels.

**1. Binding (local, offline).** Confirms that the quote's report_data is the deal hash:

```
python check_attestation.py deals/offer-002.json attestations/offer-002.json   # OK
```

**2. Signature chain (Phala's quote verifier).** Confirms that the quote was produced by real TDX hardware with a valid Intel certificate chain:

```bash
python -c "import json;print(json.dumps({'hex': json.load(open('attestations/offer-002.json'))['quote']}))" > q.json
curl -s -X POST https://cloud-api.phala.com/api/v1/attestations/verify -H "Content-Type: application/json" -d @q.json
```

Look for `"success": true` and `"quote": {"verified": true, ...}`. Also check that `quote.body.reportdata` is `0x<deal_hash>` followed by 64 zeros. The response's `checksum` opens a human-readable report at `https://proof.t16z.com/reports/<checksum>` (the TEE Attestation Explorer). Phala uses its own checksum for this, which is not the `quote_sha256` stored in the deal.

Checked for offer-002 on 2026-11-26: `success: true`, `quote.verified: true`, report data `0x8d25ba49…60f4ed` followed by zeros. Report: https://proof.t16z.com/reports/82d461b8ff9cf0b6fb1c4d84ca3bb841caca52cbd1a42fb5b4dee8aec574257e

**3. What ran in the TEE (Trust Center).** Levels 1 and 2 prove that *some* TDX VM signed the deal hash. To prove it was *this* attest-service, use [Phala's Trust Center](https://github.com/Phala-Network/trust-center) (`dstack-verifier`). It verifies the quote with DCAP-QVL and recomputes the OS measurements (MRTD and RTMR0-2). It also checks the RTMR3 event log's compose hash (from `event_log`) against the app's on-chain allowed compose hashes, which ties the quote to `attest-service/docker-compose.yml`. For fully local, trustless verification, build the Trust Center verifier, which bundles `dcap-qvl`, from that repo.

## Demo results

Both deals were settled with a 0.001 ETH deposit on Ethereum mainnet:

| Deal | Attested | Transaction |
|---|---|---|
| offer-001 | after settlement | https://etherscan.io/tx/0x98ac14ff362b4dc4fec30552cfe4b0b2d1eaac882eea9491ae99855495c4de46 |
| offer-002 | before the payment request | https://etherscan.io/tx/0x09142db39adc06b448ab043c519684b507953cf6e95327b886f422158c3de126 |

offer-002 needed three payment requests: the first two were unreachable in the Tangem app, so they're marked `EXPIRED` in `settlements.json`.

## How the tamper check works

`deal_hash` is the SHA-256 of the canonical JSON of `terms` (keys sorted, no whitespace, UTF-8). `deal_hash` itself sits outside `terms`, so it isn't part of the hashed data.

Every term, including the settlement amount and recipient address, is inside `terms`. If a field changes, even by one character, the hash no longer matches, so you can't quietly swap the payee or the amount. For example, raising the salary by 5000 without updating the hash makes `verify_deal.py` print `TAMPERED`, and `settle` refuses to create a payment request.

```
python verify_deal.py deals/offer-001.json   # OK
```

The deal file's `status` field is outside `terms`, so it can change from `agreed` to `settled` without breaking the hash.
