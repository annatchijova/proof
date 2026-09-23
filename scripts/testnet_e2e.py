"""
testnet_e2e.py — Real end-to-end test against Stellar Testnet.

This script:
1. Generates two keypairs (sender and recipient).
2. Funds the sender via Friendbot.
3. Submits a real payment transaction on Testnet.
4. Runs PROOF's verify_payment against the real transaction hash.
5. Prints the verdict, checks, and seal.

This is NOT a unit test — it requires network access and submits a
real transaction to the Stellar Testnet. It validates the full path:
  payment claim -> Stellar Testnet acquisition -> deterministic evidence
  extraction -> adjudication -> sealed evidence bundle -> independent
  verification -> user-visible result.

Usage:
  python scripts/testnet_e2e.py
"""
import sys
import time

sys.path.insert(0, ".")

from stellar_sdk import (
    Keypair,
    Network,
    Server,
    TransactionBuilder,
    Asset,
)

from proof.claim import PaymentClaim
from proof.engine import verify_payment
from proof.verifier import verify_bundle

HORIZON_TESTNET = "https://horizon-testnet.stellar.org"
NETWORK_PASSPHRASE = Network.TESTNET_NETWORK_PASSPHRASE


def fund_via_friendbot(address: str) -> None:
    """Fund a testnet account via Friendbot."""
    import requests
    resp = requests.get(
        f"https://friendbot.stellar.org?addr={address}",
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Friendbot failed: {resp.status_code} {resp.text}")
    print(f"  Funded {address[:10]}... via Friendbot")


def main() -> None:
    print("=== PROOF End-to-End Testnet Verification ===\n")

    # Step 1: Generate keypairs.
    print("1. Generating keypairs...")
    sender_kp = Keypair.random()
    recipient_kp = Keypair.random()
    sender = sender_kp.public_key
    recipient = recipient_kp.public_key
    print(f"   Sender:    {sender}")
    print(f"   Recipient: {recipient}")

    # Step 2: Fund the sender via Friendbot.
    print("\n2. Funding sender via Friendbot...")
    fund_via_friendbot(sender)
    # Wait for the account to be available on Horizon.
    time.sleep(5)

    # Step 3: Submit a real payment transaction.
    print("\n3. Submitting real payment transaction on Testnet...")
    server = Server(horizon_url=HORIZON_TESTNET)
    sender_account = server.load_account(sender)

    # Send 100 XLM (1000000000 stroops) to the recipient.
    # The recipient doesn't exist yet, so we use create_account (which
    # the extractor handles as a payment-type operation).
    amount = "100.0000000"
    tx = (
        TransactionBuilder(
            source_account=sender_account,
            network_passphrase=NETWORK_PASSPHRASE,
            base_fee=100,
        )
        .append_create_account_op(
            destination=recipient,
            starting_balance=amount,
        )
        .add_text_memo("INV-TEST-184")
        .set_timeout(30)
        .build()
    )
    tx.sign(sender_kp)
    response = server.submit_transaction(tx)
    tx_hash = response["hash"]
    print(f"   Transaction submitted: {tx_hash}")
    print(f"   Ledger: {response.get('ledger', 'unknown')}")

    # Wait for Horizon to index the transaction.
    time.sleep(3)

    # Step 4: Run PROOF verify_payment against the real transaction.
    print("\n4. Running PROOF verify_payment...")
    claim = PaymentClaim(
        transaction_hash=tx_hash,
        sender=sender,
        recipient=recipient,
        asset_code="XLM",
        amount_stroops=1000000000,
        reference="INV-TEST-184",
    )
    bundle = verify_payment(claim, network="testnet")

    print(f"\n   Verdict:  {bundle.verdict}")
    print(f"   Seal:     {bundle.seal}")
    print(f"   Checks:")
    for check in bundle.checks:
        print(f"     {check['name']:30s} {check['status']:10s} {check.get('detail', '')}")

    # Step 5: Independent verification of the bundle.
    print("\n5. Independent verification of the sealed bundle...")
    report = verify_bundle(bundle.to_dict())
    print(f"   seal_ok:            {report['seal_ok']}")
    print(f"   version_ok:         {report['version_ok']}")
    print(f"   verdict_consistent: {report['verdict_consistent']}")

    # Step 6: Summary.
    print("\n=== Summary ===")
    print(f"  Transaction:  {tx_hash}")
    print(f"  Verdict:      {bundle.verdict}")
    print(f"  Seal:         {bundle.seal}")
    print(f"  Verified:     {report['seal_ok'] and report['verdict_consistent']}")

    if bundle.verdict == "VERIFIED" and report["seal_ok"]:
        print("\n  END-TO-END PATH VALIDATED: real Testnet tx -> VERIFIED -> seal verified")
        sys.exit(0)
    else:
        print("\n  END-TO-END PATH FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
