# CONTRIBUTING TO PROOF

**Repository:** `https://github.com/annatchijova/proof`
**Author:** Anna Tchijova
**Last updated:** September 2026

> Esta guía también está disponible en español: [`CONTRIBUYENDO.md`](CONTRIBUYENDO.md)

---

## A note from the author

PROOF is not perfect, and I know it.

This is not a disclaimer. It is a design principle. A verification
system that cannot document its own failure modes is untrustworthy by
definition. The same epistemic standard I apply to evidence, I apply
to this codebase.

If you find something wrong — a bug, a case where the verdict is
incorrect, a determinism failure, a coverage gap — I want to know. I
will not be defensive about it. Criticism is not an attack on the
project. Criticism *is* the project working as intended.

Please be direct.

---

## Protocol freeze

The PROOF protocol and Soroban contract are **frozen** as of v0.1.0.
The following are frozen and will not change except to fix a confirmed
bug:

- Soroban contract `proof-registry` v0.1.0
- Commitment hash: `SHA-256(canonical(CommitmentTerms))`, version 1
- Evidence bundle schema version 1
- Verdicts: `VERIFIED`, `NOT_VERIFIED`, `INSUFFICIENT_EVIDENCE`
- Check statuses: `PASS`, `FAIL`, `ABSTAIN`
- Public API surface and authorization model
- MCP tools

**What is allowed after freeze:**

- Bug fixes confirmed by evidence
- Tests
- Deployment wiring
- UI/demo polish
- Documentation
- Product validation

**What is not allowed:**

- New capabilities
- Protocol/schema/semantic changes
- Public-write shortcuts
- Adding a funded identity merely to make the demo more impressive

If your contribution requires a protocol or schema change, open an
issue first to discuss whether it qualifies as a bug fix or requires
a protocol v2.

---

## What PROOF does not cover

PROOF verifies ledger-provable facts: transaction existence, success,
sender, recipient, asset, amount, ledger, time range, and memo. It
does not verify:

- That goods or services were delivered
- That a debt was legally satisfied
- That the person controlling a wallet is a specific human
- That the committed terms are true (only that they were committed)

If you contribute a feature that claims to verify any of the above,
it will not be merged. These are out of scope by design, not by
oversight.

---

## How to contribute

### Reporting issues

Open a GitHub issue. Include:

- PROOF version or commit hash
- The specific input (transaction hash, claim fields) that triggers
  the issue
- Observed output vs. expected output
- Whether this is a correctness issue (wrong verdict), a determinism
  issue (inconsistent output on identical input), or a usability issue

For security vulnerabilities, read [`SECURITY.md`](SECURITY.md) first.
Do not open public issues for security bugs.

### Code contributions

1. Fork the repository
2. Create a branch with a descriptive name
3. Run the full test suite before submitting: `pytest tests/ -v`
4. Regressions are not acceptable. If your patch introduces a
   regression, it requires explicit justification, evidence, and
   maintainer approval in the PR description.
5. All new code touching the verdict decision path must include a
   determinism test — identical input must produce identical output
6. If your contribution modifies verdict logic, include a
   corresponding update to `TECHNICAL.md` if it resolves a documented
   limitation, or a new entry if it introduces one
7. No float in the decision path. Use `fractions.Fraction` or
   integers. Floats are allowed only in the cosmetic display layer,
   never in a value that gets sealed
8. The LLM (if any) must not influence any sealed value. The
   deterministic engine produces and seals the result before any
   narrative layer runs

### Test contributions

New test cases must follow the existing test structure in `tests/`.
Each test must discriminate, not merely execute. A test that runs a
check without pinning its exact boundary verifies nothing.

For integration tests against live Testnet transactions, use the
reproducible transaction documented in `README.md`:

- Payment tx: `0ef76485729ca2704ea73ff3fc65f7d156c286bacc52bd8d36d19deace4de669`
- Payment ledger: `4821215`
- Expected verdict: `VERIFIED`
- Evidence seal: `c6d21734805d59886bc9a629893eb108a0666c74a03ed6e19e5abdc50e1b7d51`

Do not submit tests that "break" the system and then classify those
as accuracy deficits. Read the accuracy framing in the red-team review
before opening issues about verdict counts.

### Documentation contributions

The codebase contains documentation in English. Translations to
Spanish are welcome. Maintain technical precision — do not simplify
terminology to make translation easier.

---

## What I will not merge

- Anything that introduces floating-point operations into the verdict
  decision path without a documented justification and a determinism
  proof
- Anything that allows an LLM to influence verdicts, seals, or any
  sealed value
- Anything that adds a public-write shortcut to the deployment without
  preserving the frozen authorization model
- Anything that claims PROOF verifies legal satisfaction, delivery of
  goods, or human identity
- Patches that "fix" INSUFFICIENT_EVIDENCE verdicts on epistemically
  ambiguous cases by forcing a VERIFIED or NOT_VERIFIED verdict
- New protocol capabilities or schema changes (post-freeze)

---

## License

All contributions are accepted under the project's Apache 2.0 license.
By submitting a pull request, you confirm that you have the right to
license your contribution under these terms.

---

*"A verification system that cannot be falsified cannot be trusted."*

*— Anna Tchijova, PROOF Project*
