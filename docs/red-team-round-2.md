# Final red-team round (post-fixes)

Date: 2026-09-23

This round attacked the current post-fixes state, including the API, MCP
receipt paths, independent bundle verifier, browser UI, and container
startup. The target was the repository and its local test/deployment
configuration. No third-party account or live write operation was used.

## Threat model

The adversary can submit claims and bundles to the public API or MCP surface,
can cause a verifier user to inspect a transaction containing attacker-chosen
ledger fields, and can influence data returned by the Stellar boundary. The
adversary cannot modify the repository, the deployed container image, or the
operator's secret outside the modeled request/data surfaces.

## Confirmed findings and remediation

| ID | Finding | Evidence | Remediation |
| --- | --- | --- | --- |
| RT-01 | Receipt endpoints trusted a caller-supplied `VERIFIED` verdict and seal without independent verification. | A synthetic bundle with a valid-format transaction hash, `VERIFIED`, and a fake 64-character seal was accepted by `/receipt`; `verify_bundle` reported `seal_ok=False`. | `5a96f1e` validates seal, version, verdict consistency, and `VERIFIED` before engine, API, MCP, or on-chain receipt use. |
| RT-02 | The independent verifier accepted an arbitrary fourth verdict and misclassified `INSUFFICIENT_EVIDENCE` with a failed lookup. | A validly sealed `BOGUS` bundle returned all checks true; an insufficient-evidence bundle with a FAIL check returned `verdict_consistent=False`. | `a676791` enforces the three verdict states and their check relationship. |
| RT-03 | The browser UI inserted ledger-derived check/scope fields through `innerHTML`. | `scope_notes`, check names, statuses, and details reached HTML sinks without escaping. | `ffedd84` renders dynamic values with `textContent` and bounded status classes; the UI contract test prevents regression. |
| RT-04 | The container identity file's permissions depended on the runtime umask. | `entrypoint.sh` wrote the file containing the signing seed without an explicit private umask. | `519d1fc` sets `umask 077` before generating the Stellar identity. |

## Discriminating checks that did not produce findings

- Stellar CLI arguments are passed as an argument list with `shell=False` and a
  fixed timeout; no command-injection path was found in the inspected client.
- The logo route serves one fixed repository path and does not interpolate a
  request path; no traversal candidate was found.
- The UI's decimal parsing is an onboarding convenience only. The API accepts
  integer stroops and the sealed Python decision path contains no float; this
  was not promoted to a protocol finding.
- Public write/authentication and rate-limit concerns remain documented
  deployment assumptions, not newly discovered post-fix bypasses.

## Verification record

- `python -m pytest tests --ignore=tests/test_api.py -q`: **153 passed**.
- Focused receipt/verifier/UI/MCP tests passed during remediation.
- The repository's fresh-clone record documents the prior full suite as **161
  passed**, plus API health smoke coverage.

## Residuals

The public deployment still needs operational rate limiting/authentication if
it is exposed beyond a controlled demo, and live API tests require reachable
Stellar Testnet. Neither is silently treated as a protocol guarantee.
