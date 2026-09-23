## What changed

<!-- State the user-visible or security-relevant outcome, not only the files
changed. Keep unrelated cleanup out of this PR. -->

## Why

<!-- Link the issue or explain the evidence that motivated the change. -->

## Verification

- [ ] I ran `python -m pytest tests/ -v` (or explain why not).
- [ ] I added or updated a discriminating test for changed behavior.
- [ ] I ran `git diff --check`.
- [ ] Documentation and examples match the current implementation.

## PROOF invariants

- [ ] No float enters `PaymentClaim`, `PaymentEvidence`, adjudication, or sealing.
- [ ] `chain_of_custody` remains outside `sealed_payload`.
- [ ] `VERIFIED`, `NOT_VERIFIED`, and `INSUFFICIENT_EVIDENCE` remain distinct.
- [ ] Unspecified claim fields remain `ABSTAIN`, not an implicit match.
- [ ] Error paths fail closed and cannot return `VERIFIED`.
- [ ] All bundles retain the three scope notes.
- [ ] The deterministic core does not accept LLM output as a sealed fact.

## Contract and compatibility impact

- [ ] No protocol/schema/API/contract semantics changed.
- [ ] If semantics changed, a protocol/design issue is linked and the impact is documented.
- [ ] Existing bundles and the independent verifier remain compatible, or the migration is explicit.

## Security and operations

- [ ] No secrets, seed phrases, or private user data are included.
- [ ] External inputs are validated at the boundary.
- [ ] CI changes do not expose secrets to untrusted pull-request code.
- [ ] Public deployment limitations remain documented.
