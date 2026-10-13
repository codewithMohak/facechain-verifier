import os
import pytest
from unittest.mock import patch, MagicMock
from src.blockchain.service import (
    is_blockchain_enabled,
    anchor_manifest_to_blockchain,
    verify_anchored_manifest,
)


def test_blockchain_disabled_operation(monkeypatch):
    monkeypatch.setenv("BLOCKCHAIN_ANCHOR_ENABLED", "false")
    assert is_blockchain_enabled() is False

    res = anchor_manifest_to_blockchain("dummy_hash")
    assert res["status"] == "unanchored"
    assert "disabled" in res["message"].lower()


def test_blockchain_anchor_revert_handling(monkeypatch):
    monkeypatch.setenv("BLOCKCHAIN_ANCHOR_ENABLED", "true")
    monkeypatch.setenv("SEPOLIA_RPC_URL", "https://dummy-rpc")
    monkeypatch.setenv("PRIVATE_KEY", "0x0000000000000000000000000000000000000000000000000000000000000001")
    monkeypatch.setenv("WALLET_ADDRESS", "0x7E5F45520F1152B70fe6672a031910E73d02e29B")

    with patch("src.blockchain.service.anchor_hash", return_value="0xmocktx"):
        mock_web3 = MagicMock()
        mock_web3.eth.wait_for_transaction_receipt.return_value = {
            "status": 0,  # Reverted
            "blockNumber": 123456,
        }
        with patch("src.blockchain.service.get_web3", return_value=mock_web3):
            res = anchor_manifest_to_blockchain("test_manifest_hash", wait_for_receipt=True)
            assert res["status"] == "failed"
            assert "reverted" in res["error"].lower()


def test_blockchain_anchor_confirmed_receipt(monkeypatch):
    monkeypatch.setenv("BLOCKCHAIN_ANCHOR_ENABLED", "true")
    monkeypatch.setenv("SEPOLIA_RPC_URL", "https://dummy-rpc")
    monkeypatch.setenv("PRIVATE_KEY", "0x0000000000000000000000000000000000000000000000000000000000000001")
    monkeypatch.setenv("WALLET_ADDRESS", "0x7E5F45520F1152B70fe6672a031910E73d02e29B")

    with patch("src.blockchain.service.anchor_hash", return_value="0xmocktx"):
        mock_web3 = MagicMock()
        mock_web3.eth.wait_for_transaction_receipt.return_value = {
            "status": 1,  # Confirmed!
            "blockNumber": 999999,
        }
        with patch("src.blockchain.service.get_web3", return_value=mock_web3):
            res = anchor_manifest_to_blockchain("test_manifest_hash", wait_for_receipt=True)
            assert res["status"] == "confirmed"
            assert res["block_number"] == 999999
            assert res["transaction_hash"] == "0xmocktx"
