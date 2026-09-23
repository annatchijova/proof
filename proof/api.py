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

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator

from .claim import PaymentClaim
from .engine import issue_receipt, verify_dispute, verify_payment

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
  .toggle.active { background: var(--blue); color: var(--bg); border-color: var(--blue); }
  .card {
    background: var(--card); border: 1px solid var(--border); border-radius: 8px;
    padding: 1.5rem; margin-bottom: 1.5rem; transition: background 0.2s, border 0.2s;
  }
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
  .footer { text-align: center; color: var(--muted); font-size: 0.8rem; margin-top: 2rem; }
</style>
</head>
<body>
  <div class="header">
    <div class="header-left">
      <h1>PROOF</h1>
      <p class="tagline" data-i18n="tagline"></p>
    </div>
    <div class="controls">
      <button class="toggle" id="lang_btn" onclick="toggleLang()">ES</button>
      <button class="toggle" id="theme_btn" onclick="toggleTheme()">&#9681;</button>
    </div>
  </div>

  <div class="card">
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

  <div id="error" class="card error hidden"></div>

  <div id="result" class="hidden">
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

  <div class="footer" data-i18n="footer"></div>

<script>
const I18N = {
  en: {
    tagline: 'Someone sends you a screenshot saying they paid. PROOF verifies what actually happened — from the Stellar ledger, not from images.',
    tx_hash_label: 'Transaction hash (64-char hex)',
    tx_hash_ph: 'e.g. 0ef76485729ca2704ea73ff3fc65f7d156c286bacc52bd8d36d19deace4de669',
    sender_label: 'Expected sender (G...) — optional',
    sender_ph: 'G...',
    recipient_label: 'Expected recipient (G...) — optional',
    recipient_ph: 'G...',
    asset_label: 'Asset code — optional',
    asset_ph: 'XLM, USDC, ...',
    amount_label: 'Amount (XLM) — optional',
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
    footer: 'PROOF — deterministic Stellar payment verification. No AI, no probabilities, no screenshots.'
  },
  es: {
    tagline: 'Alguien te manda una captura diciendo que te pagó. PROOF verifica qué pasó realmente — desde el ledger de Stellar, no desde imágenes.',
    tx_hash_label: 'Hash de transacción (64 chars hex)',
    tx_hash_ph: 'ej. 0ef76485729ca2704ea73ff3fc65f7d156c286bacc52bd8d36d19deace4de669',
    sender_label: 'Sender esperado (G...) — opcional',
    sender_ph: 'G...',
    recipient_label: 'Recipient esperado (G...) — opcional',
    recipient_ph: 'G...',
    asset_label: 'Codigo de asset — opcional',
    asset_ph: 'XLM, USDC, ...',
    amount_label: 'Monto (XLM) — opcional',
    reference_label: 'Referencia/memo esperado — opcional',
    reference_ph: 'ej. INV-184',
    network_label: 'Red',
    verify_btn: 'Verificar Pago',
    verifying: 'Verificando...',
    seal_label: 'Bundle de evidencia sellado (SHA-256)',
    th_check: 'Check', th_status: 'Estado', th_detail: 'Detalle',
    tx_required: 'El hash de transaccion es obligatorio.',
    error_prefix: 'Error: ',
    net_error: 'Error de red: ',
    note_prefix: 'Nota: ',
    footer: 'PROOF — verificacion determinista de pagos Stellar. Sin IA, sin probabilidades, sin capturas.'
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
    scopeDiv.innerHTML = '<br>' + bundle.scope_notes.map(n => t.note_prefix + n).join('<br>');
  } else {
    scopeDiv.textContent = '';
  }

  const tbody = document.getElementById('checks_body');
  tbody.innerHTML = '';
  for (const check of bundle.checks) {
    const tr = document.createElement('tr');
    tr.innerHTML = '<td>' + check.name + '</td>' +
      '<td class="status-' + check.status + '">' + check.status + '</td>' +
      '<td>' + (check.detail || '') + '</td>';
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

    receipt_obj = issue_receipt(bundle)
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
