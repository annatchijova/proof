# Installation

**English** | [Español](#español)

---

## English

### Prerequisites

- **Python 3.12+** (required for the core, API, and MCP server)
- **Stellar CLI 28.0.0+** (only if you want Soroban on-chain endpoints)
- **Rust 1.75+ with `soroban-sdk 22`** (only if you want to build the contract)

The core verification engine and HTTP API need only Python. Soroban
on-chain commitment/receipt endpoints need the Stellar CLI. Building
the contract from source needs Rust.

### Quick start (core + API)

```bash
git clone https://github.com/annatchijova/proof.git
cd proof

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

uvicorn proof.api:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in your browser.

### Command-line verification (no API)

```bash
python -c "
from proof import PaymentClaim, verify_payment

claim = PaymentClaim(
    transaction_hash='your_tx_hash_here',
)
bundle = verify_payment(claim, network='testnet')
print(bundle.verdict)
print(bundle.seal)
"
```

### MCP server

```bash
python -m proof.mcp_server
```

The MCP server runs over stdio. It exposes 8 tools: 4 verification,
4 Soroban on-chain.

### Stellar CLI (optional — Soroban endpoints only)

The Stellar CLI is needed for `/commit`, `/onchain/register-receipt`,
`/onchain/commitment`, and `/onchain/receipt`. Without it, read-only
verification (`/verify`, `/health`) works fine.

```bash
# Linux x86_64
curl -sL https://github.com/stellar/stellar-cli/releases/download/v28.0.0/stellar-cli-28.0.0-x86_64-unknown-linux-gnu.tar.gz \
    | tar xz -C /usr/local/bin
stellar --version
```

Configure the Testnet network:

```bash
stellar network add --global testnet \
    --rpc-url https://soroban-testnet.stellar.org:443 \
    --network-passphrase "Test SDF Network ; September 2015" \
    --horizon-url https://horizon-testnet.stellar.org
```

If you want write endpoints (commitment/receipt registration), create
a Stellar identity:

```bash
stellar keys generate alice --network testnet
```

This identity must be funded on Testnet (via Friendbot) for writes to
succeed. Reads work without funding.

### Building the Soroban contract (optional)

```bash
cd soroban/proof-registry
soroban contract build
soroban contract deploy --source alice --network testnet
```

The contract is already deployed on Testnet at
`CDY3VWVDMRNMPGENYV4BCVNVVGLUWF76TQTSOJOOBOPG4XXLTEH7NT4I`.
You only need to build and deploy if you want your own instance.

### Docker

```bash
docker build -t proof-api .
docker run -p 8080:8080 \
    -e STELLAR_SEED_PHRASE="your seed phrase" \
    proof-api
```

The Dockerfile installs the Stellar CLI, Python dependencies, and
configures the Testnet network automatically. Pass the seed phrase
via environment variable (never in the image).

### Running the tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

161 tests covering: canonical serialization, claim validation,
adjudication, tamper detection, determinism, multi-operation
extraction, path payments, account merge, memo types, commitment
hashing, receipt issuance, dispute resolution, API/MCP boundary
validation, and Stellar client error handling.

### End-to-end against real Testnet

```bash
python scripts/testnet_e2e.py
```

This script generates real keypairs, funds an account via Friendbot,
submits a real payment to Testnet, and verifies it with PROOF
end-to-end.

### Dependencies

| Package | Version | Required for |
|---------|---------|--------------|
| `stellar-sdk` | >= 12.0, < 17.0 | Horizon API queries |
| `fastapi` | >= 0.100 | HTTP API |
| `uvicorn` | >= 0.20 | ASGI server |
| `mcp` | >= 1.0 | MCP server |
| `pytest` | >= 8.0 | Tests (dev) |
| `pytest-asyncio` | >= 0.20 | Tests (dev) |
| `httpx` | >= 0.24 | Tests (dev) |
| `soroban-sdk` | 22 | Contract (Rust, optional) |
| Stellar CLI | 28.0.0 | Soroban endpoints (optional) |

---

<a name="español"></a>

## Español

### Requisitos previos

- **Python 3.12+** (obligatorio para el core, API, y MCP server)
- **Stellar CLI 28.0.0+** (solo si querés los endpoints de Soroban)
- **Rust 1.75+ con `soroban-sdk 22`** (solo si querés compilar el contrato)

El engine de verificación y la API HTTP necesitan solo Python. Los
endpoints de commitment/receipt on-chain de Soroban necesitan el
Stellar CLI. Compilar el contrato desde el código necesita Rust.

### Inicio rápido (core + API)

```bash
git clone https://github.com/annatchijova/proof.git
cd proof

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

uvicorn proof.api:app --host 0.0.0.0 --port 8000
```

Abrí `http://localhost:8000` en tu navegador.

### Verificación por línea de comandos (sin API)

```bash
python -c "
from proof import PaymentClaim, verify_payment

claim = PaymentClaim(
    transaction_hash='tu_tx_hash_aqui',
)
bundle = verify_payment(claim, network='testnet')
print(bundle.verdict)
print(bundle.seal)
"
```

### MCP server

```bash
python -m proof.mcp_server
```

El MCP server corre sobre stdio. Expone 8 tools: 4 de verificación,
4 de Soroban on-chain.

### Stellar CLI (opcional — solo endpoints de Soroban)

El Stellar CLI se necesita para `/commit`,
`/onchain/register-receipt`, `/onchain/commitment`, y
`/onchain/receipt`. Sin él, la verificación read-only (`/verify`,
`/health`) funciona bien.

```bash
# Linux x86_64
curl -sL https://github.com/stellar/stellar-cli/releases/download/v28.0.0/stellar-cli-28.0.0-x86_64-unknown-linux-gnu.tar.gz \
    | tar xz -C /usr/local/bin
stellar --version
```

Configurá la red Testnet:

```bash
stellar network add --global testnet \
    --rpc-url https://soroban-testnet.stellar.org:443 \
    --network-passphrase "Test SDF Network ; September 2015" \
    --horizon-url https://horizon-testnet.stellar.org
```

Si querés endpoints de escritura (registro de commitments/receipts),
creá una identidad Stellar:

```bash
stellar keys generate alice --network testnet
```

Esta identidad debe estar fondeada en Testnet (vía Friendbot) para que
los writes funcionen. Los reads funcionan sin fondos.

### Compilar el contrato Soroban (opcional)

```bash
cd soroban/proof-registry
soroban contract build
soroban contract deploy --source alice --network testnet
```

El contrato ya está desplegado en Testnet en
`CDY3VWVDMRNMPGENYV4BCVNVVGLUWF76TQTSOJOOBOPG4XXLTEH7NT4I`. Solo
necesitás compilarlo y desplegarlo si querés tu propia instancia.

### Docker

```bash
docker build -t proof-api .
docker run -p 8080:8080 \
    -e STELLAR_SEED_PHRASE="tu seed phrase" \
    proof-api
```

El Dockerfile instala el Stellar CLI, las dependencias de Python, y
configura la red Testnet automáticamente. Pasá la seed phrase vía
environment variable (nunca en la imagen).

### Correr los tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

161 tests cubriendo: serialización canónica, validación de claims,
adjudicación, detección de tampering, determinismo, extracción
multi-operación, path payments, account merge, tipos de memo,
hashing de commitments, emisión de receipts, resolución de disputas,
validación de boundary API/MCP, y manejo de errores del Stellar
client.

### End-to-end contra Testnet real

```bash
python scripts/testnet_e2e.py
```

Este script genera keypairs reales, fondea una cuenta vía Friendbot,
envía un pago real a Testnet, y lo verifica con PROOF end-to-end.

### Dependencias

| Paquete | Versión | Requerido para |
|---------|---------|----------------|
| `stellar-sdk` | >= 12.0, < 17.0 | Queries a Horizon API |
| `fastapi` | >= 0.100 | HTTP API |
| `uvicorn` | >= 0.20 | ASGI server |
| `mcp` | >= 1.0 | MCP server |
| `pytest` | >= 8.0 | Tests (dev) |
| `pytest-asyncio` | >= 0.20 | Tests (dev) |
| `httpx` | >= 0.24 | Tests (dev) |
| `soroban-sdk` | 22 | Contrato (Rust, opcional) |
| Stellar CLI | 28.0.0 | Endpoints de Soroban (opcional) |
