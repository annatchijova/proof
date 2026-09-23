//! proof-registry — Soroban contract for PROOF commitments and receipts.
//!
//! This contract is a tamper-evident on-chain registry. It stores:
//!   - Commitments: a reference (e.g. invoice number) mapped to a commitment hash
//!   - Receipts: a transaction hash mapped to a seal (SHA-256 of the evidence bundle)
//!
//! The contract does NOT verify payments. All verification logic lives in the
//! off-chain Python core. The contract provides persistent, queryable storage
//! that the Python core can read and write via Soroban RPC.
//!
//! What the contract proves:
//!   - That a commitment hash was registered at a specific ledger by a specific account.
//!   - That a receipt seal was registered at a specific ledger.
//!   - That a commitment was registered before a receipt (temporal order).
//!
//! What the contract does NOT prove:
//!   - That the payment happened (that's the off-chain core's job).
//!   - That the committed terms are true (only that they were committed).
//!   - That the seal corresponds to a valid verification (only that it was stored).

#![no_std]

use soroban_sdk::{
    contract, contractimpl, contracttype, symbol_short, Address, BytesN, Env, Map, String, Symbol,
    Vec,
};

/// A commitment registered on-chain before a payment occurs.
/// Maps a reference (e.g. "INV-184") to a commitment hash (SHA-256 of the
/// canonical payment terms).
#[contracttype]
#[derive(Clone, Eq, PartialEq)]
pub struct Commitment {
    /// The reference string (e.g. invoice number).
    pub reference: String,
    /// The commitment hash (SHA-256 of canonical payment terms).
    pub commitment_hash: BytesN<32>,
    /// The account that registered the commitment.
    pub committer: Address,
    /// The ledger sequence when the commitment was registered.
    pub ledger: u32,
    /// The timestamp when the commitment was registered.
    pub timestamp: u64,
}

/// A receipt registered on-chain after a payment is verified.
/// Maps a transaction hash to a seal (SHA-256 of the evidence bundle).
#[contracttype]
#[derive(Clone, Eq, PartialEq)]
pub struct Receipt {
    /// The transaction hash of the verified payment.
    pub transaction_hash: String,
    /// The seal of the evidence bundle (SHA-256).
    pub seal: BytesN<32>,
    /// The verdict produced by the off-chain core.
    pub verdict: String,
    /// The ledger sequence when the receipt was registered.
    pub ledger: u32,
    /// The timestamp when the receipt was registered.
    pub timestamp: u64,
}

/// Storage keys.
const COMMITMENTS: Symbol = symbol_short!("COMMITS");
const RECEIPTS: Symbol = symbol_short!("RECEIPTS");

#[contract]
pub struct ProofRegistry;

#[contractimpl]
impl ProofRegistry {
    /// Register a commitment on-chain.
    ///
    /// The committer authorizes this call. The commitment hash is the
    /// SHA-256 of the canonical payment terms (computed off-chain).
    /// Once registered, a commitment cannot be overwritten — it is immutable.
    pub fn register_commitment(
        env: Env,
        committer: Address,
        reference: String,
        commitment_hash: BytesN<32>,
    ) -> Commitment {
        committer.require_auth();

        let ledger = env.ledger().sequence();
        let timestamp = env.ledger().timestamp();

        let commitment = Commitment {
            reference: reference.clone(),
            commitment_hash,
            committer: committer.clone(),
            ledger,
            timestamp,
        };

        let mut commitments: Map<String, Commitment> = env
            .storage()
            .persistent()
            .get(&COMMITMENTS)
            .unwrap_or_else(|| Map::new(&env));

        // Immutability: a commitment cannot be overwritten.
        if commitments.contains_key(reference.clone()) {
            panic!("commitment already exists for this reference");
        }

        commitments.set(reference, commitment.clone());
        env.storage().persistent().set(&COMMITMENTS, &commitments);

        commitment
    }

    /// Register a receipt on-chain.
    ///
    /// The receipt seal is the SHA-256 of the evidence bundle (computed
    /// off-chain). Once registered, a receipt cannot be overwritten.
    pub fn register_receipt(
        env: Env,
        registrar: Address,
        transaction_hash: String,
        seal: BytesN<32>,
        verdict: String,
    ) -> Receipt {
        registrar.require_auth();

        let ledger = env.ledger().sequence();
        let timestamp = env.ledger().timestamp();

        let receipt = Receipt {
            transaction_hash: transaction_hash.clone(),
            seal,
            verdict,
            ledger,
            timestamp,
        };

        let mut receipts: Map<String, Receipt> = env
            .storage()
            .persistent()
            .get(&RECEIPTS)
            .unwrap_or_else(|| Map::new(&env));

        // Immutability: a receipt cannot be overwritten.
        if receipts.contains_key(transaction_hash.clone()) {
            panic!("receipt already exists for this transaction");
        }

        receipts.set(transaction_hash, receipt.clone());
        env.storage().persistent().set(&RECEIPTS, &receipts);

        receipt
    }

    /// Get a commitment by reference.
    pub fn get_commitment(env: Env, reference: String) -> Option<Commitment> {
        let commitments: Map<String, Commitment> = env
            .storage()
            .persistent()
            .get(&COMMITMENTS)
            .unwrap_or_else(|| Map::new(&env));
        commitments.get(reference)
    }

    /// Get a receipt by transaction hash.
    pub fn get_receipt(env: Env, transaction_hash: String) -> Option<Receipt> {
        let receipts: Map<String, Receipt> = env
            .storage()
            .persistent()
            .get(&RECEIPTS)
            .unwrap_or_else(|| Map::new(&env));
        receipts.get(transaction_hash)
    }

    /// Check that a commitment was registered before a receipt.
    ///
    /// This verifies temporal order on-chain: the commitment must have been
    /// registered at an earlier ledger than the receipt. This is the
    /// on-chain version of the `commitment_precedes_payment` check.
    ///
    /// Returns:
    ///   - 0: commitment does not exist
    ///   - 1: receipt does not exist
    ///   - 2: commitment was registered after or at the same ledger as the receipt
    ///   - 3: commitment was registered before the receipt (success)
    pub fn verify_temporal_order(
        env: Env,
        reference: String,
        transaction_hash: String,
    ) -> u32 {
        let commitment = Self::get_commitment(env.clone(), reference);
        if commitment.is_none() {
            return 0;
        }
        let commitment = commitment.unwrap();

        let receipt = Self::get_receipt(env, transaction_hash);
        if receipt.is_none() {
            return 1;
        }
        let receipt = receipt.unwrap();

        if commitment.ledger < receipt.ledger {
            return 3;
        }
        return 2;
    }

    /// List all commitment references.
    pub fn list_commitments(env: Env) -> Vec<String> {
        let commitments: Map<String, Commitment> = env
            .storage()
            .persistent()
            .get(&COMMITMENTS)
            .unwrap_or_else(|| Map::new(&env));
        commitments.keys()
    }

    /// List all receipt transaction hashes.
    pub fn list_receipts(env: Env) -> Vec<String> {
        let receipts: Map<String, Receipt> = env
            .storage()
            .persistent()
            .get(&RECEIPTS)
            .unwrap_or_else(|| Map::new(&env));
        receipts.keys()
    }
}

#[cfg(test)]
mod test {
    use super::*;
    use soroban_sdk::testutils::Address as _;
    use soroban_sdk::testutils::Ledger as _;

    #[test]
    fn test_register_and_get_commitment() {
        let env = Env::default();
        let contract_id = env.register(ProofRegistry, ());
        let client = ProofRegistryClient::new(&env, &contract_id);

        let committer = Address::generate(&env);
        let reference = String::from_str(&env, "INV-184");
        let hash_bytes = [0u8; 32];
        let commitment_hash = BytesN::from_array(&env, &hash_bytes);

        env.mock_all_auths();

        let commitment = client.register_commitment(
            &committer,
            &reference,
            &commitment_hash,
        );

        assert_eq!(commitment.reference, reference);
        assert_eq!(commitment.commitment_hash, commitment_hash);
        assert_eq!(commitment.committer, committer);

        let fetched = client.get_commitment(&reference);
        assert!(fetched.is_some());
        assert_eq!(fetched.unwrap().reference, reference);
    }

    #[test]
    fn test_commitment_is_immutable() {
        let env = Env::default();
        let contract_id = env.register(ProofRegistry, ());
        let client = ProofRegistryClient::new(&env, &contract_id);

        let committer = Address::generate(&env);
        let reference = String::from_str(&env, "INV-184");
        let hash_bytes = [0u8; 32];
        let commitment_hash = BytesN::from_array(&env, &hash_bytes);

        env.mock_all_auths();

        client.register_commitment(&committer, &reference, &commitment_hash);

        // Second registration should panic.
        let result = client.try_register_commitment(
            &committer,
            &reference,
            &commitment_hash,
        );
        assert!(result.is_err());
    }

    #[test]
    fn test_register_and_get_receipt() {
        let env = Env::default();
        let contract_id = env.register(ProofRegistry, ());
        let client = ProofRegistryClient::new(&env, &contract_id);

        let registrar = Address::generate(&env);
        let tx_hash = String::from_str(&env, "abcdef1234567890");
        let seal_bytes = [1u8; 32];
        let seal = BytesN::from_array(&env, &seal_bytes);
        let verdict = String::from_str(&env, "VERIFIED");

        env.mock_all_auths();

        let receipt = client.register_receipt(&registrar, &tx_hash, &seal, &verdict);

        assert_eq!(receipt.transaction_hash, tx_hash);
        assert_eq!(receipt.seal, seal);
        assert_eq!(receipt.verdict, verdict);

        let fetched = client.get_receipt(&tx_hash);
        assert!(fetched.is_some());
        assert_eq!(fetched.unwrap().transaction_hash, tx_hash);
    }

    #[test]
    fn test_receipt_is_immutable() {
        let env = Env::default();
        let contract_id = env.register(ProofRegistry, ());
        let client = ProofRegistryClient::new(&env, &contract_id);

        let registrar = Address::generate(&env);
        let tx_hash = String::from_str(&env, "abcdef1234567890");
        let seal_bytes = [1u8; 32];
        let seal = BytesN::from_array(&env, &seal_bytes);
        let verdict = String::from_str(&env, "VERIFIED");

        env.mock_all_auths();

        client.register_receipt(&registrar, &tx_hash, &seal, &verdict);

        // Second registration should panic.
        let result = client.try_register_receipt(&registrar, &tx_hash, &seal, &verdict);
        assert!(result.is_err());
    }

    #[test]
    fn test_verify_temporal_order_success() {
        let env = Env::default();
        let contract_id = env.register(ProofRegistry, ());
        let client = ProofRegistryClient::new(&env, &contract_id);

        let committer = Address::generate(&env);
        let reference = String::from_str(&env, "INV-184");
        let commitment_hash = BytesN::from_array(&env, &[0u8; 32]);

        env.mock_all_auths();

        // Register commitment at ledger 1.
        env.ledger().set_sequence_number(1);
        client.register_commitment(&committer, &reference, &commitment_hash);

        // Register receipt at ledger 10.
        env.ledger().set_sequence_number(10);
        let tx_hash = String::from_str(&env, "abcdef1234567890");
        let seal = BytesN::from_array(&env, &[1u8; 32]);
        let verdict = String::from_str(&env, "VERIFIED");
        client.register_receipt(&committer, &tx_hash, &seal, &verdict);

        // Temporal order: commitment (ledger 1) before receipt (ledger 10).
        let result = client.verify_temporal_order(&reference, &tx_hash);
        assert_eq!(result, 3);
    }

    #[test]
    fn test_verify_temporal_order_failure() {
        let env = Env::default();
        let contract_id = env.register(ProofRegistry, ());
        let client = ProofRegistryClient::new(&env, &contract_id);

        let committer = Address::generate(&env);
        let reference = String::from_str(&env, "INV-184");
        let commitment_hash = BytesN::from_array(&env, &[0u8; 32]);

        env.mock_all_auths();

        // Register commitment at ledger 10.
        env.ledger().set_sequence_number(10);
        client.register_commitment(&committer, &reference, &commitment_hash);

        // Register receipt at ledger 5 (before commitment).
        env.ledger().set_sequence_number(5);
        let tx_hash = String::from_str(&env, "abcdef1234567890");
        let seal = BytesN::from_array(&env, &[1u8; 32]);
        let verdict = String::from_str(&env, "VERIFIED");
        client.register_receipt(&committer, &tx_hash, &seal, &verdict);

        // Temporal order: commitment (ledger 10) after receipt (ledger 5).
        let result = client.verify_temporal_order(&reference, &tx_hash);
        assert_eq!(result, 2);
    }

    #[test]
    fn test_verify_temporal_order_missing_commitment() {
        let env = Env::default();
        let contract_id = env.register(ProofRegistry, ());
        let client = ProofRegistryClient::new(&env, &contract_id);

        let reference = String::from_str(&env, "INV-184");
        let tx_hash = String::from_str(&env, "abcdef1234567890");

        let result = client.verify_temporal_order(&reference, &tx_hash);
        assert_eq!(result, 0);
    }

    #[test]
    fn test_verify_temporal_order_missing_receipt() {
        let env = Env::default();
        let contract_id = env.register(ProofRegistry, ());
        let client = ProofRegistryClient::new(&env, &contract_id);

        let committer = Address::generate(&env);
        let reference = String::from_str(&env, "INV-184");
        let commitment_hash = BytesN::from_array(&env, &[0u8; 32]);

        env.mock_all_auths();
        client.register_commitment(&committer, &reference, &commitment_hash);

        let tx_hash = String::from_str(&env, "abcdef1234567890");
        let result = client.verify_temporal_order(&reference, &tx_hash);
        assert_eq!(result, 1);
    }
}
