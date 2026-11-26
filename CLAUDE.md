# DealProof Settle

Demo: tamper-evident deal files, attested inside a TEE, then settled as ETH payment requests from the user's Tangem wallet.

- `deals/*.json`: a deal has `terms` (including `terms.settlement`) and `deal_hash` = sha256 of the canonical JSON of `terms` (`sort_keys=True`, separators `(",", ":")`, UTF-8). The settlement amount and recipient are inside `terms`, so changing them also makes the deal TAMPERED. `status` and `attestation` sit outside `terms`, so updating them doesn't change the hash.
- `verify_deal.py <deal file>`: prints `OK` (exit 0) or `TAMPERED` (exit 1).
- `check_attestation.py <deal file> <attest response json>`: prints `OK` only if the TDX quote's report_data starts with the deal's `deal_hash`.
- `attest-service/docker-compose.yml`: a Phala Cloud (dstack) service. `POST /attest {deal_hash}` returns `{deal_hash, quote, event_log}`, and `GET /health` returns `ok`.
- `settlements.json`: a JSON array of settlement records.

## Config

- `ATTEST_URL`: `https://7689ab1feadf9a96d7d08c7c41489613277ede01-8000.dstack-pha1-prod9.phala.network` (the public URL of the deployed attest-service on Phala Cloud, with no trailing slash). Below, `<ATTEST_URL>` means this value. If it is empty or unreachable, `settle` must refuse.

## Workflow: `settle <deal file>`

1. Run `python verify_deal.py <deal file>`.
   - If it prints anything other than `OK`, **stop**. Do not call attest or any Tangem tool, and do not create an intent. Report that the deal is TAMPERED.
2. If the deal's `status` is already `settled`, or `settlements.json` already has a record with this `deal_hash`, stop and report it. Never create a duplicate intent.
3. **Attest**: `POST <ATTEST_URL>/attest` with JSON `{"deal_hash": "<deal_hash>"}` (e.g. `curl -sf -X POST -H "Content-Type: application/json" -d '{"deal_hash":"..."}' <ATTEST_URL>/attest -o <scratchpad>/attest.json`). Save the response in the scratchpad, not the repo.
   - If the request fails (placeholder URL, network error, non-2xx response, invalid JSON), or `python check_attestation.py <deal file> <scratchpad>/attest.json` prints anything other than `OK`, **stop**. Do not call any Tangem tool and do not create an intent. Report that attestation FAILED.
   - Build the quote reference: `{"url": "<ATTEST_URL>/attest", "quote_prefix": <first 16 bytes of the quote, as 32 hex chars>, "quote_sha256": <sha256 of the full quote bytes>, "attested_at": <UTC ISO-8601>}`.
   - Write it to the deal as the top-level `attestation` field (outside `terms`, so `deal_hash` stays the same).
4. Call `mcp__tangem__wallets__get_tokens`. Find the entry where `networkId` == `terms.settlement.networkId` and `tokenId` == `terms.settlement.tokenId`, and use its address as `fromAddress`. If there are several addresses, ask the user which one to use.
5. Call `mcp__tangem__transactions__send_transaction` with:
   `amount` = `terms.settlement.amount`, `networkId`, `tokenId`, `toAddress` = `terms.settlement.toAddress`, `fromAddress`, `sendNotification: true`, `comment: "DealProof <deal_id> <deal_hash>"`.
6. Append `{deal_id, deal_hash, intentId, deeplink, timestamp (UTC ISO-8601), status: "CREATED", attestation: <the same quote reference>}` to `settlements.json`. Set the deal's `status` to `"settlement_pending"`. Do not touch `terms` or `deal_hash`.
7. Tell the user to approve and sign the request in the Tangem app (push notification or deeplink). Nothing moves until they sign.
8. Status check: the Tangem tool must not be polled in a loop. Call `mcp__tangem__transactions__get_transaction_status` once now, then again each time the user says they've signed.
   - `CREATED`: still unsigned. Leave the record pending.
   - `COMPLETED`: set the record's `status: "COMPLETED"` and `txHash`, set the deal's `status` to `"settled"`, and give the user `https://etherscan.io/tx/<txHash>` (the app reports it before the network confirms).
9. After writing, re-run `verify_deal.py` to confirm the deal is still `OK`.

Note: `check_attestation.py` checks only that the quote is bound to the deal (report_data == deal_hash). It does not verify Intel's signature chain. For full verification, use a DCAP quote verifier (e.g. Phala's attestation verification service).
