# Checkpoint 2 — Frozen demo scope

This is the scope presented for the Argentina Builder Challenge Checkpoint 2.
It is intentionally narrower than the full repository surface.

## Official user journey

PROOF receives a payment claim and checks it against a real Stellar Testnet
transaction.

1. A claim that matches the ledger produces `VERIFIED`.
2. The same transaction with one changed claim property produces
   `NOT_VERIFIED`.
3. A transaction that cannot be established produces
   `INSUFFICIENT_EVIDENCE`.

The official public example is:

- deployment: `https://proof-api-1028999311218.us-central1.run.app`
- payment transaction:
  `0ef76485729ca2704ea73ff3fc65f7d156c286bacc52bd8d36d19deace4de669`
- payment ledger: `4821215`
- network: Stellar Testnet
- existing Soroban commitment: reference `INV-TEST-129650`, ledger `4821217`
- existing Soroban receipt: payment ledger `4821218`, verdict `VERIFIED`

The operator has manually confirmed that the public UI loads, the example
returns `VERIFIED`, the individual checks and seal are visible, and the
transaction and operations resolve in Horizon Testnet.

## What is in scope

- the public read-only UI;
- Stellar Testnet ledger acquisition;
- claim-versus-ledger checks;
- the three verdicts above;
- the sealed EvidenceBundle and visible SHA-256 seal;
- the Horizon transaction and operations links;
- the explicit scope boundaries shown by the product.

Soroban may be shown only as existing Testnet commitment/receipt evidence.
Public writes are not part of this demo and remain disabled.

## What is deliberately out of scope

The following are implemented repository surfaces or future operational work,
but are not Checkpoint 2 demo requirements:

- MCP and dispute flows;
- creating new commitments or receipts during the demo;
- public Soroban writes;
- architecture internals, canonicalization code, or verifier implementation;
- authentication, rate limiting, additional providers, and browser automation;
- product-market validation or claims of human identity, delivery, debt
  satisfaction, or facts outside the ledger.

Leaving these out is the frozen presentation boundary, not an incomplete
Checkpoint 2 feature.

## Evidence provenance

The current UI example and the historical Soroban validation report describe
different executions. The canonical Checkpoint 2 execution is internally
consistent: payment `0ef764...` at ledger `4821215`, commitment ledger
`4821217`, and receipt ledger `4821218` with the UI seal. The report's payment
is `dde823...` at ledger `4821041`, with its own commitment, receipt, and seal;
that is a separate historical end-to-end Soroban run, not metadata for the UI
payment. Both executions coexist on Testnet without contradiction.
