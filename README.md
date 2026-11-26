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
wallets__get_tokens ─▶ transactions__send_transaction (sendNotification: true)
      │
      ▼
settlements.json += {deal_hash, intentId, deeplink, timestamp}; deal → settlement_pending
      │  user signs in the Tangem app
      ▼
transactions__get_transaction_status ─COMPLETED─▶ record txHash; deal → settled
```

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
