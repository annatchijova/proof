# PROOF speaker notes

These notes support the [pitch deck](pitch-deck.md). They are written for a
live mixed audience: say the plain-language claim first, then show the
mechanism only when it helps the audience understand the result.

## Three-minute delivery

### 0:00–0:25 — Open on the problem

Say:

> A screenshot can show that someone wants us to believe they paid. It cannot
> show that the payment happened, or that it matched the claim. PROOF starts
> with the public ledger instead of the image.

Pause after “public ledger”. Let the audience recognize the problem before
naming Stellar or SHA-256.

### 0:25–0:55 — Name the product

Say:

> PROOF takes a Stellar transaction hash and optional assertions — sender,
> recipient, asset, amount, reference, and ledger window. It reconstructs the
> payment facts from Horizon and compares each assertion independently.

Point at the first three steps of the architecture diagram. Do not explain
every module yet.

### 0:55–1:20 — Explain the verdicts

Say:

> There are three outcomes. `VERIFIED` means every applicable check passed.
> `NOT_VERIFIED` means we looked and a claim failed. `INSUFFICIENT_EVIDENCE`
> means we could not retrieve or extract enough to decide. Those are different
> facts, so PROOF keeps them different.

Use the hand gesture or cursor to separate “looked and failed” from “could not
look”. This distinction is more important than the enum names.

### 1:20–2:05 — Run the positive demo

Load the real Testnet example. Before clicking Verify, say:

> This is a real Testnet transaction already linked from the product. The UI
> is not trusting the screenshot; it is asking the ledger.

Click Verify. While the response is visible, point to the checks first, then
the verdict, then the seal. Do not read the full hash aloud.

### 2:05–2:30 — Run the adversarial demo

Change only the amount. Say:

> Now the transaction is unchanged, but the claim says 200 instead of 100.
> The ledger is still there; the claim no longer matches it.

Verify again and show `NOT_VERIFIED`. This is the proof point; do not add
extra explanation while the result is on screen.

### 2:30–2:50 — Explain integrity

Say:

> The result is a deterministic bundle. Amounts are integer stroops, the
> payload is canonically serialized, and its SHA-256 seal can be recomputed by
> an independent verifier. Change a sealed fact and the verifier rejects it.

### 2:50–3:00 — Close on the contribution

Say:

> PROOF verifies what the ledger can prove, not what a screenshot claims. It
> turns a payment claim into a reproducible evidence artifact with explicit
> boundaries.

End there. Do not close on future work or limitations.

## Q&A anchors

**“Does VERIFIED prove the invoice was legally paid?”**

> No. It proves the applicable ledger assertions passed. Legal satisfaction is
> outside the evidence PROOF has.

**“Does it prove the person who paid?”**

> No. It proves a wallet signed the transaction. A wallet signature is not
> human identity.

**“What happens when Horizon is unavailable?”**

> PROOF fails closed with `INSUFFICIENT_EVIDENCE`; it does not guess
> `VERIFIED`.

**“Why not just use the screenshot as evidence?”**

> An image has no authoritative connection to the ledger. The transaction hash
> gives PROOF a public fact source that other parties can query independently.

**“Can the seal be changed if someone changes the timestamp?”**

> Retrieval metadata such as `fetched_at` is outside the seal. The claim,
> evidence, checks, verdict, and scope notes are inside it. That lets custody
> metadata change without changing the facts the verdict rests on.

**“What is the one thing PROOF does not currently know?”**

> It does not know whether goods were delivered or who controls a wallet in
> human terms. I would need external evidence for those claims.
