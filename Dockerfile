FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates libdbus-1-3 \
    && rm -rf /var/lib/apt/lists/*

# Install the Stellar CLI (prebuilt binary from official release).
RUN curl -sL https://github.com/stellar/stellar-cli/releases/download/v28.0.0/stellar-cli-28.0.0-x86_64-unknown-linux-gnu.tar.gz \
    | tar xz -C /usr/local/bin \
    && chmod +x /usr/local/bin/stellar \
    && stellar --version

WORKDIR /app

COPY pyproject.toml ./
COPY proof/ ./proof/
COPY scripts/ ./scripts/
RUN pip install --no-cache-dir .

# Runtime configuration via environment variables.
# PROOF_CONTRACT_ID  — Soroban contract ID on Testnet
# PROOF_STELLAR_NETWORK — "testnet" (default)
# PROOF_STELLAR_SOURCE — stellar CLI identity name (default "alice")
# STELLAR_SEED_PHRASE — seed phrase for the CLI identity (secret, passed via env)
# PORT — HTTP port (set by Cloud Run, default 8080)

ENV PROOF_CONTRACT_ID=CDY3VWVDMRNMPGENYV4BCVNVVGLUWF76TQTSOJOOBOPG4XXLTEH7NT4I
ENV PROOF_STELLAR_NETWORK=testnet
ENV PROOF_STELLAR_SOURCE=alice

# Entrypoint: create the CLI identity from the seed phrase, then start uvicorn.
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8080

CMD ["/entrypoint.sh"]
