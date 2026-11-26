# DealProof Settle

Demo: tamper-evident deal files, settled as ETH payment requests from the user's Tangem wallet.

- `deals/*.json`: a deal has `terms` (including `terms.settlement`) and `deal_hash` = sha256 of the canonical JSON of `terms` (`sort_keys=True`, separators `(",", ":")`, UTF-8). The settlement amount and recipient are inside `terms`, so changing them also makes the deal TAMPERED.
- `verify_deal.py <deal file>`: prints `OK` (exit 0) or `TAMPERED` (exit 1).
- `settlements.json`: a JSON array of settlement records.

## Workflow: `settle <deal file>`

1. Run `python verify_deal.py <deal file>`.
   - If it prints anything other than `OK`, **stop**. Do not call any Tangem tool and do not create an intent. Report that the deal is TAMPERED.
2. If the deal's `status` is already `settled`, or `settlements.json` already has a record with this `deal_hash`, stop and report it. Never create a duplicate intent.
3. Call `mcp__tangem__wallets__get_tokens`. Find the entry where `networkId` == `terms.settlement.networkId` and `tokenId` == `terms.settlement.tokenId`, and use its address as `fromAddress`. If there are several addresses, ask the user which one to use.
4. Call `mcp__tangem__transactions__send_transaction` with:
   `amount` = `terms.settlement.amount`, `networkId`, `tokenId`, `toAddress` = `terms.settlement.toAddress`, `fromAddress`, `sendNotification: true`, `comment: "DealProof <deal_id> <deal_hash>"`.
5. Append `{deal_id, deal_hash, intentId, deeplink, timestamp (UTC ISO-8601), status: "CREATED"}` to `settlements.json`, and set the deal's `status` to `"settlement_pending"`. Do not touch `terms` or `deal_hash`.
6. Tell the user to approve and sign the request in the Tangem app (push notification or deeplink). Nothing moves until they sign.
7. Status check: the Tangem tool must not be polled in a loop. Call `mcp__tangem__transactions__get_transaction_status` once now, then again each time the user says they've signed.
   - `CREATED`: still unsigned. Leave the record pending.
   - `COMPLETED`: set the record's `status: "COMPLETED"` and `txHash`, set the deal's `status` to `"settled"`, and give the user `https://etherscan.io/tx/<txHash>` (the app reports it before the network confirms).
8. After writing, re-run `verify_deal.py` to confirm the deal is still `OK`.
