"""
api.py — HTTP API for PROOF verification.

Exposes the deterministic core via a REST API so third parties can
verify payment claims without running the full pipeline locally.

Endpoints:
  GET  /                — user-facing verification UI
  POST /verify          — verify a single payment claim
  POST /verify/dispute  — verify a dispute between two claims
  POST /receipt         — issue a receipt from a verified bundle
  GET  /health          — health check

The API is a thin transport layer. All logic lives in the deterministic
core. The API never modifies verdicts, seals, or evidence.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field, field_validator

from .claim import PaymentClaim
from .engine import _validate_receipt_bundle, issue_receipt, verify_dispute, verify_payment

app = FastAPI(
    title="PROOF — Payment Evidence, Not Screenshots",
    description="Verify Stellar payment claims from the ledger, not from images.",
    version="0.4.0",
)


class VerifyRequest(BaseModel):
    """Request body for POST /verify."""
    transaction_hash: str = Field(..., description="64-char hex Stellar transaction hash")
    sender: str | None = Field(None, description="Expected sender address (G...)")
    recipient: str | None = Field(None, description="Expected recipient address (G...)")
    asset_code: str | None = Field(None, description="Expected asset code (e.g. USDC)")
    asset_issuer: str | None = Field(None, description="Expected asset issuer address")
    amount_stroops: int | None = Field(None, description="Expected amount in stroops (integer)")
    reference: str | None = Field(None, description="Expected reference/memo")
    ledger_min: int | None = Field(None, description="Minimum ledger sequence")
    ledger_max: int | None = Field(None, description="Maximum ledger sequence")
    commitment_tx_hash: str | None = Field(None, description="Transaction hash of an on-chain commitment")
    network: str = Field("testnet", description="Stellar network: testnet or mainnet")

    @field_validator("network")
    @classmethod
    def validate_network(cls, v: str) -> str:
        if v not in ("testnet", "mainnet"):
            raise ValueError("network must be 'testnet' or 'mainnet'")
        return v

    def to_claim(self) -> PaymentClaim:
        return PaymentClaim(
            transaction_hash=self.transaction_hash,
            sender=self.sender,
            recipient=self.recipient,
            asset_code=self.asset_code,
            asset_issuer=self.asset_issuer,
            amount_stroops=self.amount_stroops,
            reference=self.reference,
            ledger_min=self.ledger_min,
            ledger_max=self.ledger_max,
            commitment_tx_hash=self.commitment_tx_hash,
        )


class DisputeRequest(BaseModel):
    """Request body for POST /verify/dispute."""
    claim_a: VerifyRequest
    claim_b: VerifyRequest


class ReceiptRequest(BaseModel):
    """Request body for POST /receipt."""
    bundle: dict = Field(..., description="A verified evidence bundle")


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


_INDEX_HTML = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Verify Stellar payment claims from the ledger, not from screenshots.">
<meta name="theme-color" content="#0d1117">
<meta property="og:title" content="PROOF — Payment Evidence, Not Screenshots">
<meta property="og:description" content="Deterministic Stellar payment verification with sealed evidence bundles.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://proof-api-1028999311218.us-central1.run.app/">
<meta property="og:image" content="https://proof-api-1028999311218.us-central1.run.app/brand/logo.png">
<meta name="twitter:card" content="summary">
<link rel="icon" type="image/png" href="/brand/logo.png">
<title>PROOF — Payment Evidence, Not Screenshots</title>
<style>
  :root[data-theme="dark"] {
    --bg: #0d1117; --card: #161b22; --border: #30363d; --text: #e6edf3;
    --muted: #8b949e; --green: #3fb950; --red: #f85149; --yellow: #d29922;
    --blue: #58a6ff; --input-bg: #0d1117;
  }
  :root[data-theme="light"] {
    --bg: #f6f8fa; --card: #ffffff; --border: #d0d7de; --text: #1f2328;
    --muted: #656d76; --green: #1a7f37; --red: #cf222e; --yellow: #9a6700;
    --blue: #0969da; --input-bg: #f6f8fa;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.5; padding: 2rem;
    max-width: 800px; margin: 0 auto; transition: background 0.2s, color 0.2s;
  }
  .header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 2rem; }
  .header-left h1 { font-size: 1.6rem; margin-bottom: 0.3rem; }
  .tagline { color: var(--muted); font-size: 0.95rem; max-width: 500px; }
  .controls { display: flex; gap: 0.5rem; align-items: center; }
  .toggle {
    background: var(--card); border: 1px solid var(--border); border-radius: 6px;
    color: var(--text); padding: 0.4rem 0.8rem; font-size: 0.8rem; cursor: pointer;
    font-weight: 600;
  }
  .toggle:hover { border-color: var(--blue); }
  :focus-visible { outline: 3px solid var(--blue); outline-offset: 2px; }
  .repo-link {
    display: inline-flex; align-items: center; gap: 0.3rem; color: var(--blue);
    text-decoration: none; font-size: 0.85rem; font-weight: 600;
  }
  .repo-link:hover { text-decoration: underline; }
  .badge {
    display: inline-block; background: rgba(88,166,255,0.15); color: var(--blue);
    border-radius: 4px; padding: 0.15rem 0.5rem; font-size: 0.7rem; font-weight: 600;
    margin-left: 0.5rem; vertical-align: middle;
  }

  /* Hero flow */
  .hero { margin-bottom: 2rem; }
  .hero-flow {
    display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;
    font-size: 0.9rem; color: var(--muted); margin: 0.8rem 0 1rem;
  }
  .hero-step {
    background: var(--card); border: 1px solid var(--border); border-radius: 6px;
    padding: 0.4rem 0.7rem; color: var(--text); font-weight: 500;
  }
  .hero-arrow { color: var(--muted); font-weight: 700; }
  .hero-cta { display: flex; gap: 1rem; align-items: center; flex-wrap: wrap; }
  .cta-btn {
    background: var(--blue); color: var(--bg); border: none; border-radius: 6px;
    padding: 0.6rem 1.2rem; font-size: 0.9rem; font-weight: 600; cursor: pointer;
    text-decoration: none; display: inline-block;
  }
  .cta-btn:hover { opacity: 0.9; }

  /* Verifier form */
  .card {
    background: var(--card); border: 1px solid var(--border); border-radius: 8px;
    padding: 1.5rem; margin-bottom: 1.5rem; transition: background 0.2s, border 0.2s;
  }
  .card h2 { font-size: 1rem; margin-bottom: 1rem; color: var(--text); }
  label { display: block; font-size: 0.85rem; color: var(--muted); margin-bottom: 0.3rem; }
  input, select {
    width: 100%; padding: 0.6rem; background: var(--input-bg); border: 1px solid var(--border);
    border-radius: 6px; color: var(--text); font-size: 0.9rem; font-family: monospace;
    margin-bottom: 1rem; transition: background 0.2s, border 0.2s;
  }
  input:focus { border-color: var(--blue); outline: none; }
  button {
    background: var(--blue); color: var(--bg); border: none; border-radius: 6px;
    padding: 0.7rem 1.5rem; font-size: 0.95rem; font-weight: 600; cursor: pointer;
    width: 100%;
  }
  button:hover { opacity: 0.9; }
  button:disabled { opacity: 0.5; cursor: wait; }
  .verdict {
    font-size: 1.4rem; font-weight: 700; text-align: center; padding: 1rem;
    border-radius: 6px; margin-bottom: 1rem;
  }
  .verdict.VERIFIED { background: rgba(63,185,80,0.15); color: var(--green); }
  .verdict.NOT_VERIFIED { background: rgba(248,81,73,0.15); color: var(--red); }
  .verdict.INSUFFICIENT_EVIDENCE { background: rgba(210,153,34,0.15); color: var(--yellow); }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  th, td { text-align: left; padding: 0.5rem; border-bottom: 1px solid var(--border); }
  th { color: var(--muted); font-weight: 600; }
  .status-PASS { color: var(--green); }
  .status-FAIL { color: var(--red); }
  .status-ABSTAIN { color: var(--yellow); }
  .seal {
    font-family: monospace; font-size: 0.8rem; color: var(--muted);
    word-break: break-all; padding: 0.5rem; background: var(--input-bg); border-radius: 4px;
  }
  .hidden { display: none; }
  .error { color: var(--red); padding: 1rem; background: rgba(248,81,73,0.1); border-radius: 6px; }
  .scope { font-size: 0.8rem; color: var(--muted); margin-top: 0.5rem; }
  .row { display: flex; gap: 1rem; }
  .row > div { flex: 1; }

  /* Testnet evidence */
  .evidence-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; margin-bottom: 0.8rem; }
  .evidence-item { font-size: 0.8rem; }
  .evidence-item .label { color: var(--muted); }
  .evidence-item .value { font-family: monospace; color: var(--text); word-break: break-all; }
  .evidence-links { display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 0.5rem; }
  .evidence-links a { color: var(--blue); font-size: 0.8rem; text-decoration: none; }
  .evidence-links a:hover { text-decoration: underline; }

  /* Secondary explanation */
  .section { margin-bottom: 1.5rem; }
  .section h2 { font-size: 0.95rem; color: var(--text); margin-bottom: 0.5rem; }
  .section p { font-size: 0.85rem; color: var(--muted); line-height: 1.5; }
  .footer { text-align: center; color: var(--muted); font-size: 0.8rem; margin-top: 2rem; }

  /* Verifier hint */
  .hint { font-size: 0.8rem; color: var(--muted); margin-bottom: 1rem; }

  /* Examples */
  .examples { margin-bottom: 1.5rem; }
  .examples h3 { font-size: 0.85rem; color: var(--blue); margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.05em; }
  .example-list { display: flex; flex-direction: column; gap: 0.5rem; }
  .example-item {
    background: var(--card); border: 1px solid var(--border); border-radius: 6px;
    color: var(--text); padding: 0.6rem 0.8rem; font-size: 0.85rem; cursor: pointer;
    text-align: left; width: 100%; font-weight: 500;
  }
  .example-item:hover { border-color: var(--blue); }
  .example-desc { font-size: 0.8rem; color: var(--muted); margin-top: 0.5rem; line-height: 1.4; }

  @media (max-width: 600px) {
    .evidence-grid { grid-template-columns: 1fr; }
    .hero-flow { font-size: 0.8rem; }
  }
</style>
</head>
<body>
  <div class="header">
    <div class="header-left">
      <h1>PROOF <span class="badge" data-i18n="badge"></span></h1>
      <p class="tagline" data-i18n="tagline"></p>
    </div>
    <div class="controls">
      <a class="repo-link" href="https://github.com/annatchijova/proof" target="_blank" rel="noopener" title="GitHub" aria-label="Open PROOF on GitHub">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
      </a>
      <button class="toggle" id="lang_btn" onclick="toggleLang()" aria-label="Switch language">ES</button>
      <button class="toggle" id="theme_btn" onclick="toggleTheme()" aria-label="Switch color theme">&#9681;</button>
    </div>
  </div>

  <div class="hero">
    <div class="hero-flow">
      <span class="hero-step" data-i18n="hero_claim"></span>
      <span class="hero-arrow">&ne;</span>
      <span class="hero-step" data-i18n="hero_evidence"></span>
      <span class="hero-arrow">&rarr;</span>
      <span class="hero-step">PROOF</span>
      <span class="hero-arrow">&rarr;</span>
      <span class="hero-step" data-i18n="hero_verify"></span>
    </div>
    <div class="hero-cta">
      <a class="cta-btn" href="#verifier" data-i18n="hero_cta"></a>
      <a class="repo-link" href="https://github.com/annatchijova/proof" target="_blank" rel="noopener" data-i18n="hero_repo"></a>
    </div>
  </div>

  <div class="card" id="verifier">
    <h2 data-i18n="verifier_title"></h2>
    <p class="hint" data-i18n="verifier_hint"></p>
    <label for="tx_hash" data-i18n="tx_hash_label"></label>
    <input type="text" id="tx_hash" data-i18n-ph="tx_hash_ph">

    <div class="row">
      <div>
        <label for="sender" data-i18n="sender_label"></label>
        <input type="text" id="sender" data-i18n-ph="sender_ph">
      </div>
      <div>
        <label for="recipient" data-i18n="recipient_label"></label>
        <input type="text" id="recipient" data-i18n-ph="recipient_ph">
      </div>
    </div>

    <div class="row">
      <div>
        <label for="asset_code" data-i18n="asset_label"></label>
        <input type="text" id="asset_code" data-i18n-ph="asset_ph">
      </div>
      <div>
        <label for="amount_xlm" data-i18n="amount_label"></label>
        <input type="number" id="amount_xlm" placeholder="100" step="0.0000001">
      </div>
    </div>

    <label for="reference" data-i18n="reference_label"></label>
    <input type="text" id="reference" data-i18n-ph="reference_ph">

    <label for="network" data-i18n="network_label"></label>
    <select id="network">
      <option value="testnet">Testnet</option>
      <option value="mainnet">Mainnet</option>
    </select>

    <button id="verify_btn" onclick="verify()" data-i18n="verify_btn"></button>
  </div>

  <div class="examples">
    <h3 data-i18n="examples_h"></h3>
    <div class="example-list">
      <button class="example-item" onclick="loadExample('verified')" data-i18n="ex_verified_btn"></button>
      <button class="example-item" onclick="loadExample('not_verified')" data-i18n="ex_not_verified_btn"></button>
      <button class="example-item" onclick="loadExample('insufficient')" data-i18n="ex_insufficient_btn"></button>
    </div>
    <p class="example-desc" id="example_desc" role="status" aria-live="polite"></p>
  </div>

  <div id="error" class="card error hidden" role="alert" aria-live="assertive"></div>

  <div id="result" class="hidden" aria-live="polite" aria-atomic="true">
    <div class="card">
      <div id="verdict" class="verdict"></div>
      <label data-i18n="seal_label"></label>
      <div id="seal" class="seal"></div>
      <div id="scope" class="scope"></div>
    </div>
    <div class="card">
      <table>
        <thead>
          <tr><th data-i18n="th_check"></th><th data-i18n="th_status"></th><th data-i18n="th_detail"></th></tr>
        </thead>
        <tbody id="checks_body"></tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <h2 data-i18n="testnet_title"></h2>
    <div class="evidence-grid">
      <div class="evidence-item"><span class="label" data-i18n="ev_verdict"></span><br><span class="value" style="color:var(--green); font-weight:700;">VERIFIED</span></div>
      <div class="evidence-item"><span class="label" data-i18n="ev_payment_ledger"></span><br><span class="value">4821215</span></div>
      <div class="evidence-item"><span class="label" data-i18n="ev_commitment_ledger"></span><br><span class="value">4821217</span></div>
      <div class="evidence-item"><span class="label" data-i18n="ev_receipt_ledger"></span><br><span class="value">4821218</span></div>
      <div class="evidence-item" style="grid-column:1/-1;"><span class="label" data-i18n="ev_seal"></span><br><span class="value">c6d21734805d59886bc9a629893eb108a0666c74a03ed6e19e5abdc50e1b7d51</span></div>
    </div>
    <div class="evidence-links">
      <a href="https://horizon-testnet.stellar.org/transactions/0ef76485729ca2704ea73ff3fc65f7d156c286bacc52bd8d36d19deace4de669" target="_blank" rel="noopener" data-i18n="ev_link_tx"></a>
      <a href="https://horizon-testnet.stellar.org/transactions/0ef76485729ca2704ea73ff3fc65f7d156c286bacc52bd8d36d19deace4de669/operations" target="_blank" rel="noopener" data-i18n="ev_link_ops"></a>
      <a href="https://github.com/annatchijova/proof/blob/main/docs/testnet-validation-report.md" target="_blank" rel="noopener" data-i18n="ev_link_report"></a>
    </div>
  </div>

  <div class="section">
    <h2 data-i18n="sec_stellar_h"></h2>
    <p data-i18n="sec_stellar_p"></p>
  </div>
  <div class="section">
    <h2 data-i18n="sec_diff_h"></h2>
    <p data-i18n="sec_diff_p"></p>
  </div>

  <div class="footer">
    <span data-i18n="footer"></span>
  </div>

<script>
const I18N = {
  en: {
    badge: 'Stellar Testnet',
    tagline: 'Someone sends you a screenshot saying they paid. PROOF verifies what actually happened — from the Stellar ledger, not from images.',
    hero_claim: 'Someone says they paid',
    hero_evidence: 'claim ≠ evidence',
    hero_verify: 'verify against Stellar',
    hero_cta: 'Verify a payment',
    hero_repo: 'View source on GitHub',
    verifier_title: 'Verify a payment',
    verifier_hint: 'Paste just a transaction hash to reconstruct what happened, or add expected fields to verify a specific claim.',
    tx_hash_label: 'Transaction hash (64-char hex)',
    tx_hash_ph: 'e.g. 0ef76485729ca2704ea73ff3fc65f7d156c286bacc52bd8d36d19deace4de669',
    sender_label: 'Expected sender (G...) — optional',
    sender_ph: 'G...',
    recipient_label: 'Expected recipient (G...) — optional',
    recipient_ph: 'G...',
    asset_label: 'Asset code — optional',
    asset_ph: 'XLM, USDC, ...',
    amount_label: 'Amount — optional',
    reference_label: 'Expected reference/memo — optional',
    reference_ph: 'e.g. INV-184',
    network_label: 'Network',
    verify_btn: 'Verify Payment',
    verifying: 'Verifying...',
    seal_label: 'Sealed evidence bundle (SHA-256)',
    th_check: 'Check', th_status: 'Status', th_detail: 'Detail',
    tx_required: 'Transaction hash is required.',
    error_prefix: 'Error: ',
    net_error: 'Network error: ',
    note_prefix: 'Note: ',
    examples_h: 'Try with a real Testnet transaction',
    ex_verified_btn: 'Payment that matches the claim → VERIFIED',
    ex_verified_desc: 'This transaction paid 100 XLM to this account. The claim matches the ledger.',
    ex_not_verified_btn: 'Claim that contradicts the ledger → NOT_VERIFIED',
    ex_not_verified_desc: 'Same real transaction, but the claim says it paid 200 XLM. The ledger shows 100. The evidence contradicts the claim.',
    ex_insufficient_btn: 'Transaction that cannot be found → INSUFFICIENT_EVIDENCE',
    ex_insufficient_desc: 'This transaction hash does not exist on Testnet. There is not enough evidence to decide.',
    testnet_title: 'Live on Stellar Testnet',
    ev_verdict: 'Verdict',
    ev_payment_ledger: 'Payment ledger',
    ev_commitment_ledger: 'Commitment ledger',
    ev_receipt_ledger: 'Receipt ledger',
    ev_seal: 'Evidence seal',
    ev_link_tx: 'Inspect transaction on Horizon',
    ev_link_ops: 'Inspect operations',
    ev_link_report: 'Validation report',
    sec_stellar_h: 'Why Stellar',
    sec_stellar_p: 'Stellar is the source of evidence: a public ledger where every transaction is independently verifiable by anyone. Soroban is the on-chain registry where PROOF commits sealed evidence — commitments and receipts are stored on-chain with enforced authorization and immutability.',
    sec_diff_h: 'What makes PROOF different',
    sec_diff_p: 'The verdict follows from explicit rules over ledger evidence, not from a probabilistic estimate. The same input always produces the same sealed result, independently reproducible with a stdlib-only verifier.',
    footer: 'PROOF — deterministic Stellar payment verification. No AI, no probabilities, no screenshots.'
  },
  es: {
    badge: 'Stellar Testnet',
    tagline: 'Alguien te manda una captura diciendo que te pagó. PROOF verifica qué pasó realmente — desde el ledger de Stellar, no desde imágenes.',
    hero_claim: 'Alguien dice que pagó',
    hero_evidence: 'claim ≠ evidencia',
    hero_verify: 'verificar contra Stellar',
    hero_cta: 'Verificar un pago',
    hero_repo: 'Ver código en GitHub',
    verifier_title: 'Verificar un pago',
    verifier_hint: 'Pegá solamente un hash de transacción para reconstruir qué ocurrió, o agregá campos esperados para verificar un claim específico.',
    tx_hash_label: 'Hash de transacción (64 chars hex)',
    tx_hash_ph: 'ej. 0ef76485729ca2704ea73ff3fc65f7d156c286bacc52bd8d36d19deace4de669',
    sender_label: 'Sender esperado (G...) — opcional',
    sender_ph: 'G...',
    recipient_label: 'Recipient esperado (G...) — opcional',
    recipient_ph: 'G...',
    asset_label: 'Código de asset — opcional',
    asset_ph: 'XLM, USDC, ...',
    amount_label: 'Monto — opcional',
    reference_label: 'Referencia/memo esperado — opcional',
    reference_ph: 'ej. INV-184',
    network_label: 'Red',
    verify_btn: 'Verificar Pago',
    verifying: 'Verificando...',
    seal_label: 'Bundle de evidencia sellado (SHA-256)',
    th_check: 'Check', th_status: 'Estado', th_detail: 'Detalle',
    tx_required: 'El hash de transacción es obligatorio.',
    error_prefix: 'Error: ',
    net_error: 'Error de red: ',
    note_prefix: 'Nota: ',
    examples_h: 'Probar con una transacción real de Testnet',
    ex_verified_btn: 'Pago que coincide con el claim → VERIFIED',
    ex_verified_desc: 'Esta transacción pagó 100 XLM a esta cuenta. El claim coincide con el ledger.',
    ex_not_verified_btn: 'Claim que contradice el ledger → NOT_VERIFIED',
    ex_not_verified_desc: 'La misma transacción real, pero el claim dice que pagó 200 XLM. El ledger muestra 100. La evidencia contradice el claim.',
    ex_insufficient_btn: 'Transacción que no se puede encontrar → INSUFFICIENT_EVIDENCE',
    ex_insufficient_desc: 'Este hash de transacción no existe en Testnet. No hay evidencia suficiente para decidir.',
    testnet_title: 'Activo en Stellar Testnet',
    ev_verdict: 'Veredicto',
    ev_payment_ledger: 'Ledger de pago',
    ev_commitment_ledger: 'Ledger de commitment',
    ev_receipt_ledger: 'Ledger de receipt',
    ev_seal: 'Seal de evidencia',
    ev_link_tx: 'Inspeccionar transacción en Horizon',
    ev_link_ops: 'Inspeccionar operaciones',
    ev_link_report: 'Reporte de validación',
    sec_stellar_h: 'Por qué Stellar',
    sec_stellar_p: 'Stellar es la fuente de evidencia: un ledger público donde cada transacción es verificable por cualquiera. Soroban es el registry on-chain donde PROOF commitea evidencia sellada — commitments y receipts se guardan on-chain con autorización e inmutabilidad enforced.',
    sec_diff_h: 'Qué hace a PROOF diferente',
    sec_diff_p: 'El veredicto surge de reglas explícitas sobre evidencia del ledger, no de una estimación probabilística. La misma entrada siempre produce el mismo resultado sellado, reproducible independientemente con un verificador stdlib-only.',
    footer: 'PROOF — verificación determinista de pagos Stellar. Sin IA, sin probabilidades, sin capturas.'
  }
};

let lang = localStorage.getItem('proof-lang') || 'en';
let theme = localStorage.getItem('proof-theme') || 'dark';

function applyI18n() {
  const t = I18N[lang];
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (t[key]) el.textContent = t[key];
  });
  document.querySelectorAll('[data-i18n-ph]').forEach(el => {
    const key = el.getAttribute('data-i18n-ph');
    if (t[key]) el.placeholder = t[key];
  });
  document.documentElement.lang = lang;
  document.getElementById('lang_btn').textContent = lang === 'en' ? 'ES' : 'EN';
}

function toggleLang() {
  lang = lang === 'en' ? 'es' : 'en';
  localStorage.setItem('proof-lang', lang);
  applyI18n();
}

function applyTheme() {
  document.documentElement.setAttribute('data-theme', theme);
  document.getElementById('theme_btn').innerHTML = theme === 'dark' ? '&#9728;' : '&#9790;';
}

function toggleTheme() {
  theme = theme === 'dark' ? 'light' : 'dark';
  localStorage.setItem('proof-theme', theme);
  applyTheme();
}

function loadExample(kind) {
  const t = I18N[lang];
  const descDiv = document.getElementById('example_desc');
  // Clear previous result
  document.getElementById('result').classList.add('hidden');
  document.getElementById('error').classList.add('hidden');

  if (kind === 'verified') {
    document.getElementById('tx_hash').value = '0ef76485729ca2704ea73ff3fc65f7d156c286bacc52bd8d36d19deace4de669';
    document.getElementById('sender').value = 'GBCGM4OPIEOSI3IADI6J67CKHKZF72WZEGBHS4BNK5MQMLCTYFDJL66O';
    document.getElementById('recipient').value = 'GDLWNTN6N2NTX5DFFIGL7PLXY6TGMYG7DPURQOXSOU3MBX5WRLLJZEWV';
    document.getElementById('asset_code').value = 'XLM';
    document.getElementById('amount_xlm').value = '100';
    document.getElementById('reference').value = 'INV-TEST-129650';
    document.getElementById('network').value = 'testnet';
    descDiv.textContent = t.ex_verified_desc;
  } else if (kind === 'not_verified') {
    document.getElementById('tx_hash').value = '0ef76485729ca2704ea73ff3fc65f7d156c286bacc52bd8d36d19deace4de669';
    document.getElementById('sender').value = 'GBCGM4OPIEOSI3IADI6J67CKHKZF72WZEGBHS4BNK5MQMLCTYFDJL66O';
    document.getElementById('recipient').value = 'GDLWNTN6N2NTX5DFFIGL7PLXY6TGMYG7DPURQOXSOU3MBX5WRLLJZEWV';
    document.getElementById('asset_code').value = 'XLM';
    document.getElementById('amount_xlm').value = '200';
    document.getElementById('reference').value = '';
    document.getElementById('network').value = 'testnet';
    descDiv.textContent = t.ex_not_verified_desc;
  } else if (kind === 'insufficient') {
    document.getElementById('tx_hash').value = 'a'.repeat(64);
    document.getElementById('sender').value = '';
    document.getElementById('recipient').value = '';
    document.getElementById('asset_code').value = '';
    document.getElementById('amount_xlm').value = '';
    document.getElementById('reference').value = '';
    document.getElementById('network').value = 'testnet';
    descDiv.textContent = t.ex_insufficient_desc;
  }
  document.getElementById('verifier').scrollIntoView({behavior:'smooth'});
}

async function verify() {
  const t = I18N[lang];
  const btn = document.getElementById('verify_btn');
  const errDiv = document.getElementById('error');
  const resultDiv = document.getElementById('result');
  btn.disabled = true;
  btn.textContent = t.verifying;
  errDiv.classList.add('hidden');
  resultDiv.classList.add('hidden');

  const txHash = document.getElementById('tx_hash').value.trim();
  if (!txHash) {
    errDiv.textContent = t.tx_required;
    errDiv.classList.remove('hidden');
    btn.disabled = false;
    btn.textContent = t.verify_btn;
    return;
  }

  const amountXlm = document.getElementById('amount_xlm').value;
  const amountStroops = amountXlm ? Math.round(parseFloat(amountXlm) * 10000000) : null;

  const body = {
    transaction_hash: txHash,
    network: document.getElementById('network').value,
  };
  const sender = document.getElementById('sender').value.trim();
  const recipient = document.getElementById('recipient').value.trim();
  const assetCode = document.getElementById('asset_code').value.trim();
  const reference = document.getElementById('reference').value.trim();
  if (sender) body.sender = sender;
  if (recipient) body.recipient = recipient;
  if (assetCode) body.asset_code = assetCode;
  if (amountStroops) body.amount_stroops = amountStroops;
  if (reference) body.reference = reference;

  try {
    const resp = await fetch('/verify', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    if (!resp.ok) {
      errDiv.textContent = t.error_prefix + (data.detail || JSON.stringify(data));
      errDiv.classList.remove('hidden');
      btn.disabled = false;
      btn.textContent = t.verify_btn;
      return;
    }
    showResult(data);
  } catch (e) {
    errDiv.textContent = t.net_error + e.message;
    errDiv.classList.remove('hidden');
  }
  btn.disabled = false;
  btn.textContent = t.verify_btn;
}

function showResult(bundle) {
  const t = I18N[lang];
  const verdictDiv = document.getElementById('verdict');
  verdictDiv.textContent = bundle.verdict;
  verdictDiv.className = 'verdict ' + bundle.verdict;

  document.getElementById('seal').textContent = bundle.seal;

  const scopeDiv = document.getElementById('scope');
  if (bundle.scope_notes && bundle.scope_notes.length > 0) {
    scopeDiv.textContent = bundle.scope_notes.map(n => t.note_prefix + n).join('\\n');
  } else {
    scopeDiv.textContent = '';
  }

  const tbody = document.getElementById('checks_body');
  tbody.innerHTML = '';
  for (const check of bundle.checks) {
    const tr = document.createElement('tr');
    const nameCell = document.createElement('td');
    nameCell.textContent = check.name || '';
    const statusCell = document.createElement('td');
    statusCell.textContent = check.status || '';
    if (['PASS', 'FAIL', 'ABSTAIN'].includes(check.status)) {
      statusCell.className = 'status-' + check.status;
    }
    const detailCell = document.createElement('td');
    detailCell.textContent = check.detail || '';
    tr.append(nameCell, statusCell, detailCell);
    tbody.appendChild(tr);
  }

  document.getElementById('result').classList.remove('hidden');
}

applyI18n();
applyTheme();
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """User-facing verification UI."""
    return _INDEX_HTML


@app.get("/brand/logo.png", include_in_schema=False)
def brand_logo() -> FileResponse:
    """Serve the repository logo for favicon and social previews."""
    logo_path = Path(__file__).resolve().parent.parent / "visual" / "logo.png"
    return FileResponse(logo_path, media_type="image/png")


@app.post("/verify")
def verify(req: VerifyRequest) -> dict[str, Any]:
    """Verify a payment claim against the Stellar ledger.

    Returns a sealed evidence bundle with the verdict, checks, and SHA-256 seal.
    """
    try:
        claim = req.to_claim()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    bundle = verify_payment(claim, network=req.network)
    return bundle.to_dict()


@app.post("/verify/dispute")
def verify_dispute_endpoint(req: DisputeRequest) -> dict[str, Any]:
    """Verify a dispute between two contradictory payment claims.

    Each claim is verified independently, then the evidence sets are
    compared for contradictions.
    """
    try:
        claim_a = req.claim_a.to_claim()
        claim_b = req.claim_b.to_claim()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Use the network from claim_a (both claims should be on the same network).
    result = verify_dispute(claim_a, claim_b, network=req.claim_a.network)
    return result.to_dict()


@app.post("/receipt")
def receipt(req: ReceiptRequest) -> dict[str, Any]:
    """Issue a receipt from a verified evidence bundle.

    The receipt contains the transaction hash, verdict, and seal. It can
    be registered on-chain via a manage_data operation.
    """
    bundle_dict = req.bundle
    if not isinstance(bundle_dict, dict):
        raise HTTPException(status_code=400, detail="bundle must be a dict")

    required_fields = {"version", "claim", "evidence", "checks", "verdict", "seal"}
    missing = required_fields - set(bundle_dict.keys())
    if missing:
        raise HTTPException(status_code=400, detail=f"bundle missing fields: {missing}")

    from .evidence import EvidenceBundle

    bundle = EvidenceBundle(
        version=bundle_dict["version"],
        claim=bundle_dict["claim"],
        evidence=bundle_dict["evidence"],
        checks=bundle_dict["checks"],
        verdict=bundle_dict["verdict"],
        scope_notes=bundle_dict.get("scope_notes", []),
        seal=bundle_dict["seal"],
        chain_of_custody=bundle_dict.get("chain_of_custody", {}),
        commitment=bundle_dict.get("commitment"),
    )

    try:
        receipt_obj = issue_receipt(bundle)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return receipt_obj.to_dict()


class CommitRequest(BaseModel):
    """Request body for POST /commit.

    Registers a commitment on the Soroban contract. The commitment hash
    is computed from the payment terms (sender, recipient, asset, amount,
    reference) using the same canonicalization as the off-chain core.
    """
    committer: str = Field(..., description="Stellar address of the committer (G...)")
    reference: str = Field(..., description="Reference string (e.g. invoice number)")
    sender: str = Field(..., description="Expected sender address (G...)")
    recipient: str = Field(..., description="Expected recipient address (G...)")
    asset_code: str = Field("XLM", description="Asset code (e.g. XLM, USDC)")
    asset_issuer: str | None = Field(None, description="Asset issuer address (None for XLM)")
    amount_stroops: int = Field(..., description="Amount in stroops (integer)")
    network: str = Field("testnet", description="Stellar network: testnet or mainnet")

    @field_validator("network")
    @classmethod
    def validate_network(cls, v: str) -> str:
        if v not in ("testnet", "mainnet"):
            raise ValueError("network must be 'testnet' or 'mainnet'")
        return v


@app.post("/commit")
def commit(req: CommitRequest) -> dict[str, Any]:
    """Register a commitment on the Soroban contract.

    Computes the commitment hash from the payment terms and registers it
    on-chain. The commitment is immutable — it cannot be overwritten.

    This endpoint does NOT verify a payment. It only commits the expected
    payment terms on-chain so that a future verification can prove the
    terms were committed before the payment occurred.
    """
    from .commitment import CommitmentTerms
    from .soroban_client import register_commitment, SorobanClientError

    try:
        terms = CommitmentTerms(
            sender=req.sender,
            recipient=req.recipient,
            asset_code=req.asset_code,
            asset_issuer=req.asset_issuer,
            amount_stroops=req.amount_stroops,
            reference=req.reference,
        )
        commitment_hash = terms.commitment_hash()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        on_chain = register_commitment(
            committer=req.committer,
            reference=req.reference,
            commitment_hash=commitment_hash,
        )
    except SorobanClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {
        "status": "committed",
        "commitment_hash": commitment_hash,
        "on_chain": {
            "reference": on_chain.reference,
            "commitment_hash": on_chain.commitment_hash,
            "committer": on_chain.committer,
            "ledger": on_chain.ledger,
            "timestamp": on_chain.timestamp,
        },
    }


class OnChainQueryRequest(BaseModel):
    """Request body for on-chain queries."""
    reference: str | None = Field(None, description="Commitment reference")
    transaction_hash: str | None = Field(None, description="Transaction hash")


@app.get("/onchain/commitment")
def get_onchain_commitment(reference: str) -> dict[str, Any]:
    """Retrieve a commitment from the Soroban contract."""
    from .soroban_client import get_commitment, SorobanClientError

    try:
        result = get_commitment(reference)
    except SorobanClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    if result is None:
        raise HTTPException(status_code=404, detail="commitment not found")

    return {
        "reference": result.reference,
        "commitment_hash": result.commitment_hash,
        "committer": result.committer,
        "ledger": result.ledger,
        "timestamp": result.timestamp,
    }


@app.get("/onchain/receipt")
def get_onchain_receipt(transaction_hash: str) -> dict[str, Any]:
    """Retrieve a receipt from the Soroban contract."""
    from .soroban_client import get_receipt, SorobanClientError

    try:
        result = get_receipt(transaction_hash)
    except SorobanClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    if result is None:
        raise HTTPException(status_code=404, detail="receipt not found")

    return {
        "transaction_hash": result.transaction_hash,
        "seal": result.seal,
        "verdict": result.verdict,
        "ledger": result.ledger,
        "timestamp": result.timestamp,
    }


@app.post("/onchain/register-receipt")
def register_onchain_receipt(req: ReceiptRequest) -> dict[str, Any]:
    """Register a receipt on the Soroban contract after verification.

    This registers the evidence bundle seal on-chain so that third
    parties can independently verify the receipt exists.
    """
    from .evidence import EvidenceBundle
    from .soroban_client import register_receipt, SorobanClientError
    import os

    bundle_dict = req.bundle
    if not isinstance(bundle_dict, dict):
        raise HTTPException(status_code=400, detail="bundle must be a dict")

    required_fields = {"version", "claim", "evidence", "checks", "verdict", "seal"}
    missing = required_fields - set(bundle_dict.keys())
    if missing:
        raise HTTPException(status_code=400, detail=f"bundle missing fields: {missing}")

    bundle = EvidenceBundle(
        version=bundle_dict["version"],
        claim=bundle_dict["claim"],
        evidence=bundle_dict["evidence"],
        checks=bundle_dict["checks"],
        verdict=bundle_dict["verdict"],
        scope_notes=bundle_dict.get("scope_notes", []),
        seal=bundle_dict["seal"],
        chain_of_custody=bundle_dict.get("chain_of_custody", {}),
        commitment=bundle_dict.get("commitment"),
    )

    try:
        _validate_receipt_bundle(bundle)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    tx_hash = bundle_dict.get("claim", {}).get("transaction_hash", "")
    if not tx_hash:
        raise HTTPException(status_code=400, detail="bundle missing transaction_hash in claim")

    registrar = os.environ.get("PROOF_STELLAR_SOURCE", "alice")

    try:
        on_chain = register_receipt(
            registrar=registrar,
            transaction_hash=tx_hash,
            seal=bundle.seal,
            verdict=bundle.verdict,
        )
    except SorobanClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {
        "status": "registered",
        "on_chain": {
            "transaction_hash": on_chain.transaction_hash,
            "seal": on_chain.seal,
            "verdict": on_chain.verdict,
            "ledger": on_chain.ledger,
            "timestamp": on_chain.timestamp,
        },
    }
