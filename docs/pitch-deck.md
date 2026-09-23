# PROOF pitch deck

This is the slide outline for a mixed technical audience. The spoken claim is
deliberately narrow: PROOF verifies whether a Stellar ledger contains facts
that match a payment claim. It does not infer delivery, legal satisfaction, or
human identity.

## Three-minute version

### 1. The problem — screenshots are not evidence

Someone says “I paid” and sends a screenshot. The image can look convincing,
but it does not answer the only question that matters: did this payment happen
on the Stellar ledger, and did it match the claim?

### 2. The product — PROOF checks the ledger

Give PROOF a transaction hash and optional assertions such as sender,
recipient, asset, amount, reference, or ledger window. PROOF reconstructs the
payment facts from Horizon and returns a sealed evidence bundle.

### 3. The result — three honest verdicts

- `VERIFIED`: every applicable assertion passed.
- `NOT_VERIFIED`: the ledger was checked and at least one assertion failed.
- `INSUFFICIENT_EVIDENCE`: the transaction could not be retrieved or extracted.

Unspecified fields are `ABSTAIN`, not “match anything”.

### 4. Live proof

Load the real Testnet example in the UI. Show the successful payment, the
checks, the verdict, and the SHA-256 seal. Then change the amount to the wrong
value and show `NOT_VERIFIED`.

### 5. Why the result is trustworthy

Amounts are integer stroops, serialization is typed and ordered, the payload
is sealed deterministically, and an independent verifier recomputes the seal.
Changing a sealed fact is detectable.

### 6. Close — evidence, not screenshots

PROOF turns a payment claim into a reproducible ledger-backed result. The
contribution is not “a nicer payment screenshot”; it is a bounded evidence
artifact that says exactly what the ledger established.

## Sixty-second version

“A payment screenshot is an image, not evidence. PROOF takes a Stellar
transaction hash and the facts someone claims — who paid, who received what,
how much, and why — then reconstructs the transaction from the public ledger.
It checks each assertion independently and returns one of three honest
outcomes: verified, not verified, or insufficient evidence. The result is a
deterministic evidence bundle sealed with SHA-256, and an independent verifier
can detect if any sealed fact changes. In the demo, we load a real Testnet
payment, get `VERIFIED`, change the amount, and immediately get
`NOT_VERIFIED`. PROOF verifies what the ledger can prove, not what a screenshot
claims.”

## Five-minute version

Use the three-minute version, then add:

1. **A commitment before payment:** show how a pre-registered commitment can
   be checked against the later payment and how Soroban stores commitments and
   receipts with authorization and immutability.
2. **The seal boundary:** show that `claim`, `evidence`, `checks`, `verdict`,
   and scope notes are sealed, while retrieval metadata remains outside the
   seal so a timestamp update does not invalidate the facts.
3. **The adversarial case:** show a wrong recipient or amount producing
   `NOT_VERIFIED`, and a missing transaction producing
   `INSUFFICIENT_EVIDENCE` rather than a false verdict.
4. **The independent check:** run `python scripts/tamper_demo.py` and point out
   that a valid bundle passes while a mutated amount fails verification.

## Claims that are safe to say aloud

- “The current repository test suite contains 161 tests.”
- “The Testnet example has been validated end-to-end and is linked from the UI.”
- “The seal covers the canonical evidence payload, not retrieval metadata.”
- “The verifier detects mutations to sealed fields.”

Avoid saying “PROOF proves the payment was legitimate”, “PROOF proves delivery”,
or “PROOF identifies the human behind the wallet”. Those claims exceed the
evidence model. Detailed timing and Q&A wording are in the
[speaker notes](speaker-notes.md).
