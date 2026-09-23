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
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PROOF — Payment Evidence, Not Screenshots</title>
<style>
  :root {
    --bg: #0d1117;
    --card: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --muted: #8b949e;
    --green: #3fb950;
    --red: #f85149;
    --yellow: #d29922;
    --blue: #58a6ff;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.5; padding: 2rem;
    max-width: 800px; margin: 0 auto;
  }
  h1 { font-size: 1.6rem; margin-bottom: 0.5rem; }
  .tagline { color: var(--muted); margin-bottom: 2rem; font-size: 0.95rem; }
  .card {
    background: var(--card); border: 1px solid var(--border); border-radius: 8px;
    padding: 1.5rem; margin-bottom: 1.5rem;
  }
  label { display: block; font-size: 0.85rem; color: var(--muted); margin-bottom: 0.3rem; }
  input, select {
    width: 100%; padding: 0.6rem; background: var(--bg); border: 1px solid var(--border);
    border-radius: 6px; color: var(--text); font-size: 0.9rem; font-family: monospace;
    margin-bottom: 1rem;
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
    word-break: break-all; padding: 0.5rem; background: var(--bg); border-radius: 4px;
  }
  .hidden { display: none; }
  .error { color: var(--red); padding: 1rem; background: rgba(248,81,73,0.1); border-radius: 6px; }
  .scope { font-size: 0.8rem; color: var(--muted); margin-top: 0.5rem; }
  .row { display: flex; gap: 1rem; }
  .row > div { flex: 1; }
</style>
</head>
<body>
  <h1>PROOF</h1>
  <p class="tagline">Someone sends you a screenshot saying they paid. PROOF verifies what actually happened — from the Stellar ledger, not from images.</p>

  <div class="card">
    <label for="tx_hash">Transaction hash (64-char hex)</label>
    <input type="text" id="tx_hash" placeholder="e.g. 086467a70920eae62efb1c7189e8bd4cd1ac3024039e93f4cb0493da046958a4">

    <div class="row">
      <div>
        <label for="sender">Expected sender (G...) — optional</label>
        <input type="text" id="sender" placeholder="G...">
      </div>
      <div>
        <label for="recipient">Expected recipient (G...) — optional</label>
        <input type="text" id="recipient" placeholder="G...">
      </div>
    </div>

    <div class="row">
      <div>
        <label for="asset_code">Asset code — optional</label>
        <input type="text" id="asset_code" placeholder="XLM, USDC, ...">
      </div>
      <div>
        <label for="amount_xlm">Amount (XLM) — optional</label>
        <input type="number" id="amount_xlm" placeholder="100" step="0.0000001">
      </div>
    </div>

    <label for="reference">Expected reference/memo — optional</label>
    <input type="text" id="reference" placeholder="e.g. INV-184">

    <label for="network">Network</label>
    <select id="network">
      <option value="testnet">Testnet</option>
      <option value="mainnet">Mainnet</option>
    </select>

    <button id="verify_btn" onclick="verify()">Verify Payment</button>
  </div>

  <div id="error" class="card error hidden"></div>

  <div id="result" class="hidden">
    <div class="card">
      <div id="verdict" class="verdict"></div>
      <label>Sealed evidence bundle (SHA-256)</label>
      <div id="seal" class="seal"></div>
      <div id="scope" class="scope"></div>
    </div>
    <div class="card">
      <table>
        <thead>
          <tr><th>Check</th><th>Status</th><th>Detail</th></tr>
        </thead>
        <tbody id="checks_body"></tbody>
      </table>
    </div>
  </div>

<script>
async function verify() {
  const btn = document.getElementById('verify_btn');
  const errDiv = document.getElementById('error');
  const resultDiv = document.getElementById('result');
  btn.disabled = true;
  btn.textContent = 'Verifying...';
  errDiv.classList.add('hidden');
  resultDiv.classList.add('hidden');

  const txHash = document.getElementById('tx_hash').value.trim();
  if (!txHash) {
    errDiv.textContent = 'Transaction hash is required.';
    errDiv.classList.remove('hidden');
    btn.disabled = false;
    btn.textContent = 'Verify Payment';
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
      errDiv.textContent = 'Error: ' + (data.detail || JSON.stringify(data));
      errDiv.classList.remove('hidden');
      btn.disabled = false;
      btn.textContent = 'Verify Payment';
      return;
    }
    showResult(data);
  } catch (e) {
    errDiv.textContent = 'Network error: ' + e.message;
    errDiv.classList.remove('hidden');
  }
  btn.disabled = false;
  btn.textContent = 'Verify Payment';
}

function showResult(bundle) {
  const verdictDiv = document.getElementById('verdict');
  verdictDiv.textContent = bundle.verdict;
  verdictDiv.className = 'verdict ' + bundle.verdict;

  document.getElementById('seal').textContent = bundle.seal;

  const scopeDiv = document.getElementById('scope');
  if (bundle.scope_notes && bundle.scope_notes.length > 0) {
    scopeDiv.innerHTML = '<br>' + bundle.scope_notes.map(n => 'Note: ' + n).join('<br>');
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
