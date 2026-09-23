# PROOF

**English** | [Español](README_ES.md) | [Technical README](TECHNICAL.md)

## The problem

Someone sends you a screenshot saying they paid. You look at it. It looks
real. But you cannot tell — a screenshot is an image, not evidence. It can
be edited, fabricated, or taken from a different transaction entirely.

The question is not "does this screenshot look real?" The question is:
**did this payment actually happen on the Stellar ledger?**

## What PROOF does

PROOF takes a Stellar transaction hash and a payment claim, reconstructs
the facts from the ledger, and produces a sealed evidence bundle with a
verdict.

```
"Alice paid Bob 100 USDC for invoice INV-184"
                    |
                    v
           Stellar ledger (transaction hash)
                    |
                    v
          Deterministic evidence extraction
                    |
                    v
          Claim vs evidence adjudication
                    |
                    v
          VERIFIED / NOT VERIFIED / INSUFFICIENT EVIDENCE
                    |
                    v
          Sealed evidence bundle (SHA-256)
```

PROOF does not look at screenshots. It looks at the ledger.

## Observable behavior

**Claim: "100 USDC from Alice to Bob for INV-184"**

```
EVIDENCE
  transaction exists          PASS
  transaction successful     PASS
  sender matches              PASS
  recipient matches           PASS
  asset matches               PASS
  amount = 100 USDC           PASS
  reference = INV-184         PASS

VERDICT: VERIFIED
Seal: sha256:...
```

**Claim: "100 USDC to Bob" (but the transaction went elsewhere)**

```
EVIDENCE
  transaction exists          PASS
  transaction successful      PASS
  amount = 100 USDC           PASS
  recipient matches           FAIL  (expected Bob, got someone else)

VERDICT: NOT VERIFIED
```

**Claim: "100 USDC paid, goods delivered"**

```
EVIDENCE
  transaction exists          PASS
  transaction successful      PASS
  amount = 100 USDC           PASS

VERDICT: VERIFIED
DELIVERY: OUTSIDE EVIDENCE SCOPE
```

PROOF verifies what the ledger can prove. It does not claim more.

## What PROOF does not prove

These are not limitations to hide — they are boundaries that make the
verdict trustworthy:

- **Payment executed is not debt satisfied.** A successful transaction
  proves the asset moved. It does not prove the underlying obligation is
  legally fulfilled.
- **Transaction exists is not goods delivered.** The ledger records
  financial events, not physical ones.
- **Wallet signed is not human identity.** A signature proves a key was
  used, not who was behind the keyboard.

## How it works

1. **Input:** a `PaymentClaim` (transaction hash + optional assertions:
   sender, recipient, asset, amount, reference, ledger window) and a
   network (testnet or mainnet).
2. **Fetch:** PROOF queries the Stellar Horizon API for the transaction
   and its operations.
3. **Extract:** payment-relevant facts are reconstructed: sender,
   recipient, asset, amount (in integer stroops), timestamp, success
   status, memo.
4. **Adjudicate:** each claim proposition is checked independently
   against the evidence. Unspecified fields are ABSTAIN, not assumed true.
5. **Seal:** the claim, evidence, checks, and verdict are canonicalized
   (typed, ordered, versioned) and sealed with SHA-256.
6. **Verify:** an independent stdlib-only verifier can recompute the seal
   and confirm the bundle was not tampered.

## Repository

```
proof/
  canonicalize.py    # typed, ordered, versioned serialization + SHA-256 seal
  claim.py           # PaymentClaim — what someone asserts happened
  evidence.py        # PaymentEvidence, CheckResult, EvidenceBundle
  stellar_client.py  # Horizon API wrapper (testnet + mainnet)
  extractor.py       # reconstruct evidence from tx + operations
  adjudicator.py     # compare claim vs evidence, produce checks + verdict
  verifier.py        # independent stdlib-only bundle verifier
  engine.py          # main entry point: verify_payment(claim, network)
tests/               # 55 tests: canonicalization, adjudication, determinism, boundary
```

## Try it

```bash
cd proof
source .venv/bin/activate

python -c "
from proof import PaymentClaim, verify_payment

claim = PaymentClaim(
    transaction_hash='your_tx_hash_here',
    network='testnet',
)
bundle = verify_payment(claim, network='testnet')
print(bundle.verdict)
print(bundle.seal)
"
```

## Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

55 tests covering: canonical serialization, claim validation, adjudication
logic, tamper detection, and determinism.

For the full architecture, threat model, and design decisions, see the
[Technical README](TECHNICAL.md).
