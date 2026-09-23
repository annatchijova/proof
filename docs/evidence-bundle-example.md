# Annotated EvidenceBundle

This is a small deterministic example of the bundle returned by PROOF. The
transaction hash and account addresses are synthetic fixtures; the structure,
field names, check states, scope notes, and seal are produced by
`EvidenceBundle.build()`.

```json
{
  "version": "1",
  "claim": {
    "transaction_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  },
  "evidence": {
    "transaction_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "ledger": 12345,
    "timestamp_unix": 1700000000,
    "successful": true,
    "sender": "GCKSJ2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z",
    "recipient": "GCXSC2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z",
    "asset_code": "XLM",
    "asset_issuer": null,
    "amount_stroops": 1000000000,
    "memo": null,
    "memo_type": "none",
    "operation_type": "payment",
    "operations": [
      {
        "operation_type": "payment",
        "sender": "GCKSJ2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z",
        "recipient": "GCXSC2OO2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z2QZ2NLM7XQ2Z",
        "asset_code": "XLM",
        "asset_issuer": null,
        "amount_stroops": 1000000000
      }
    ]
  },
  "checks": [
    {
      "name": "transaction_exists",
      "status": "PASS",
      "expected": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "actual": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "detail": "found"
    },
    {
      "name": "transaction_successful",
      "status": "PASS",
      "expected": "success",
      "actual": "success",
      "detail": "ok"
    }
  ],
  "verdict": "VERIFIED",
  "scope_notes": [
    "Payment execution does not establish legal satisfaction of any underlying debt.",
    "Transaction existence does not establish delivery of goods or services.",
    "Wallet signature does not establish human identity."
  ],
  "seal": "0791885657cb66778c2631ec010eb77badbd26e2e6566786a7f51ccd9813f0fe",
  "chain_of_custody": {
    "network": "testnet"
  }
}
```

## What each part means

| Part | Meaning | Inside the seal? |
|---|---|---|
| `claim` | What the requester asserted. This example asserts only that a transaction hash exists. | Yes |
| `evidence` | Facts reconstructed from the Stellar ledger, including integer stroops and operations. | Yes |
| `checks` | Individual propositions and their `PASS`, `FAIL`, or `ABSTAIN` status. | Yes |
| `verdict` | The deterministic result of the applicable checks. | Yes |
| `scope_notes` | The three boundaries PROOF always communicates. | Yes |
| `seal` | SHA-256 over the canonical sealed payload. | It is the result, not an input |
| `chain_of_custody` | Retrieval metadata such as network and fetch time. | No |

Because the claim contains no sender, recipient, asset, or amount assertion,
those propositions are not silently treated as matches: the adjudicator would
represent them as `ABSTAIN` when it evaluates the full claim. The example is
therefore only evidence that the transaction was found and successful.

Changing any field covered by the seal — for example `amount_stroops`, a
check, or the verdict — makes independent verification fail. Changing
`chain_of_custody` does not invalidate the seal because retrieval metadata is
deliberately outside the sealed payload.
