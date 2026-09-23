# Fresh-clone reproducibility check

This is the shortest clean-room verification of the documented installation
path. It starts from a shallow clone and does not rely on the working tree,
virtual environment, caches, or uncommitted files of the development checkout.

## Procedure

```bash
git clone --depth 1 https://github.com/annatchijova/proof.git proof-clean
cd proof-clean
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest tests/ -q
python -m uvicorn proof.api:app --host 127.0.0.1 --port 8000
```

In a second terminal, query the local health endpoint:

```bash
curl -sS http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## Observed result

The procedure was run from a fresh clone of `origin/main` on 2026-09-23:

- editable installation completed successfully;
- all **161 tests passed** in 7.03 seconds;
- the API started with the documented command;
- `/health` returned `{"status":"ok"}`.

The Testnet-dependent adversarial checks remain guarded by the repository's
existing skip behavior, so this check proves local reproducibility and API
startup, not the continued availability of historical Testnet transactions.
