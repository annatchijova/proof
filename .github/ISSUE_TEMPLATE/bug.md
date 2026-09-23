---
name: Bug report
about: Report an incorrect verdict, broken boundary, or reproducible product defect
title: "bug: "
labels: bug
assignees: ""
---

## Before opening

- [ ] I checked `SECURITY.md` and this is not a vulnerability report.
- [ ] I searched existing issues for the same behavior.
- [ ] I can reproduce this against a specific commit.

## Classification

- [ ] Incorrect verdict (`VERIFIED`, `NOT_VERIFIED`, or `INSUFFICIENT_EVIDENCE`)
- [ ] Evidence or seal mismatch
- [ ] API/MCP boundary failure
- [ ] UI or documentation bug
- [ ] Other reproducible defect

## Reproduction

**Commit or version:**

**Command or endpoint:**

**Input:**

<!-- Redact secrets. For a payment claim, include the network and transaction
hash when safe to share, plus the asserted fields. -->

## Observed behavior

```text

```

## Expected behavior

```text

```

## Invariant affected

<!-- For example: no floats in the decision path, fail closed, ABSTAIN for
unspecified fields, seal excludes chain_of_custody, or scope notes present. -->

## Additional context

<!-- Logs, test output, screenshots, or the smallest useful fixture. -->
