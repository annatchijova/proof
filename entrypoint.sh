#!/bin/bash
set -euo pipefail
# Keep the generated Stellar identity (which contains the signing seed)
# private even if the container's default umask is permissive.
umask 077

# Create the stellar CLI identity from the seed phrase if provided.
# This is needed for Soroban contract invocations (read and write).
SEED_PHRASE="${STELLAR_SEED_PHRASE:-}"
SOURCE_IDENTITY="${PROOF_STELLAR_SOURCE:-alice}"

if [ -n "$SEED_PHRASE" ]; then
    IDENTITY_DIR="$HOME/.config/stellar/identity"
    mkdir -p "$IDENTITY_DIR"
    cat > "$IDENTITY_DIR/${SOURCE_IDENTITY}.toml" <<EOF
seed_phrase = "${SEED_PHRASE}"
EOF
    echo "Stellar CLI identity '${SOURCE_IDENTITY}' configured."
else
    echo "WARNING: STELLAR_SEED_PHRASE not set. Soroban endpoints will fail."
    echo "Read-only verification (POST /verify, GET /health) will still work."
fi

# Configure the testnet network for the stellar CLI.
stellar network add --global testnet \
    --rpc-url https://soroban-testnet.stellar.org:443 \
    --network-passphrase "Test SDF Network ; September 2015" \
    --horizon-url https://horizon-testnet.stellar.org 2>/dev/null || true

# Start the API server.
PORT="${PORT:-8080}"
exec uvicorn proof.api:app --host 0.0.0.0 --port "$PORT"
