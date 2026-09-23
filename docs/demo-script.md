# PROOF live demo script

Target length: 90 seconds. The demo shows one real ledger-backed verification
and one deliberate claim mismatch. It does not depend on a funded identity or
on writing to the chain.

## Before the room

1. Open the deployed UI or a local `uvicorn` instance.
2. Confirm the page loads and the theme/language controls respond.
3. Click the verified Testnet example once and confirm the ledger is available.
4. Keep the [tamper demo](../scripts/tamper_demo.py) available locally as a
   no-network fallback.
5. Do not type or display seed phrases, private keys, or credentials.

## Live sequence

### 0:00 — Set the frame

Say: “I will show a real Testnet payment, then change only the claim. The
transaction stays the same.”

### 0:10 — Load the positive example

Click “Payment that matches the claim → VERIFIED”. Point out that the form is
now populated with a real transaction hash and explicit assertions.

### 0:20 — Verify

Click “Verify Payment”. Wait for the response. Point in this order:

1. individual checks;
2. `VERIFIED` verdict;
3. sealed evidence bundle and SHA-256 seal.

Say: “The UI is showing a result reconstructed from the Stellar ledger, not
judging an image.”

### 0:45 — Mutate only the claim

Click “Payment that contradicts the ledger → NOT_VERIFIED”, or change the
amount from `100` to `200` while leaving the transaction hash unchanged.

Click “Verify Payment”. Point at the failed amount check.

Say: “The payment exists, but this claim does not match it. That is
`NOT_VERIFIED`, not a network failure.”

### 1:05 — Show the third state if time allows

Click “Transaction that cannot be found → INSUFFICIENT_EVIDENCE”. Say: “This
one means PROOF could not establish enough evidence. It is deliberately not
collapsed into `NOT_VERIFIED`.”

### 1:20 — Close

Say: “One transaction, three possible epistemic outcomes, and a sealed bundle
that an independent verifier can check.”

## No-network fallback

If the Testnet example is unavailable, do not invent a successful live result.
Say: “The ledger endpoint is unavailable, so the correct product state is
`INSUFFICIENT_EVIDENCE`. I will show the local integrity property instead.”

Run:

```bash
python scripts/tamper_demo.py
```

Expected output includes:

```text
valid bundle:    seal_ok=True
tampered amount: seal_ok=False
```

This fallback demonstrates seal enforcement, not live Testnet availability.

## Recovery rules

- If the first request is slow, wait once; do not submit repeatedly.
- If the API returns an error, read the specific error and state that the
  result is not evidence of a payment.
- If the UI shows a stale result after loading another example, reload before
  continuing; never present a stale verdict as the new claim's result.
- If asked whether PROOF proves delivery, legal satisfaction, or human
  identity, answer “No; those are outside the ledger evidence scope.”
