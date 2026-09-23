"""
test_canonicalize.py — Tests for the canonical serialization and sealing.

Each test states the invariant it defends and what mutation it would catch.
"""
import hashlib
import json

from proof.canonicalize import CANONICALIZE_VERSION, canonical_bytes, canonicalize, seal


def test_bool_and_int_are_distinguishable():
    """Invariant: bool and int must not collide — bool subclasses int in Python.

    Mutation caught: if bool check were removed, True and 1 would hash the same.
    """
    assert canonicalize(True) != canonicalize(1)
    assert canonicalize(False) != canonicalize(0)
    assert canonicalize(True) == "true"
    assert canonicalize(1) == "1:int"


def test_str_and_int_are_distinguishable():
    """Invariant: "1" and 1 must produce different canonical forms.

    Mutation caught: if type tags were removed, string "1" and int 1 would collide.
    """
    assert canonicalize("1") != canonicalize(1)
    assert canonicalize("1") == "1"
    assert canonicalize(1) == "1:int"


def test_none_is_explicit():
    """Invariant: None is "null", not omitted or zero.

    Mutation caught: if None were dropped, {"a": None} and {} would collide.
    """
    assert canonicalize(None) == "null"
    assert canonicalize({"a": None}) != canonicalize({})


def test_dict_keys_are_sorted():
    """Invariant: dict key order must not affect the canonical bytes.

    Mutation caught: if sort_keys were removed, {"a":1,"b":2} and {"b":2,"a":1}
    would produce different bytes.
    """
    a = canonical_bytes({"b": 2, "a": 1})
    b = canonical_bytes({"a": 1, "b": 2})
    assert a == b


def test_nested_dict_keys_are_sorted():
    """Invariant: sorting is recursive.

    Mutation caught: if only top-level keys were sorted, nested dicts would
    still leak insertion order.
    """
    a = canonical_bytes({"x": {"z": 1, "y": 2}})
    b = canonical_bytes({"x": {"y": 2, "z": 1}})
    assert a == b


def test_list_order_is_preserved():
    """Invariant: list order is semantically meaningful and must be preserved.

    Mutation caught: if lists were sorted, [1,2] and [2,1] would collide.
    """
    assert canonical_bytes([1, 2]) != canonical_bytes([2, 1])


def test_seal_is_deterministic():
    """Invariant: same input always produces the same SHA-256 seal.

    Mutation caught: if any nondeterministic element were introduced,
    two calls would produce different seals.
    """
    payload = {"x": 1, "y": [True, "hello", None], "z": {"a": 42}}
    assert seal(payload) == seal(payload)


def test_seal_changes_on_payload_change():
    """Invariant: a different payload produces a different seal.

    Mutation caught: if the seal ignored any field, changing that field
    would not change the seal.
    """
    a = seal({"x": 1})
    b = seal({"x": 2})
    assert a != b


def test_seal_is_sha256():
    """Invariant: the seal is a SHA-256 hex digest.

    Mutation caught: if the algorithm were changed, the digest would differ.
    """
    payload = {"test": "value"}
    expected = hashlib.sha256(canonical_bytes(payload)).hexdigest()
    assert seal(payload) == expected
    assert len(seal(payload)) == 64


def test_version_is_stamped():
    """Invariant: CANONICALIZE_VERSION exists and is a string.

    Mutation caught: if the version were removed, old bundles couldn't be
    distinguished from new ones.
    """
    assert isinstance(CANONICALIZE_VERSION, str)
    assert CANONICALIZE_VERSION == "1"
