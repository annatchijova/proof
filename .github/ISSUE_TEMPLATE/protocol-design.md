---
name: Protocol or design proposal
about: Propose a change that may affect the frozen protocol, schema, or trust model
title: "design: "
labels: design
assignees: ""
---

## Status against the protocol freeze

- [ ] This is documentation, UI, deployment wiring, or a confirmed bug fix.
- [ ] This may change the evidence bundle schema.
- [ ] This may change verdict or check semantics.
- [ ] This may change the Soroban contract or public API.

<!-- If any of the last three boxes is checked, explain why this is not a
protocol v2, or explicitly request a protocol-freeze decision. -->

## Problem

What real user, security, or operational problem does this solve?

## Proposed behavior

Describe the smallest change that would solve it.

## Invariants and scope

- What remains deterministically sealed?
- What remains outside the seal?
- How do `PASS`, `FAIL`, `ABSTAIN`, and the three verdicts behave?
- Which existing scope note or limitation changes, if any?

## Compatibility and migration

What happens to existing bundles, verifiers, API consumers, and on-chain
records?

## Verification plan

List the tests, fixtures, or falsifiers that would distinguish the proposal
from the current behavior.
