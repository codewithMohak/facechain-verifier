import os
from dotenv import load_dotenv
from web3 import Web3
from src.utils.hashing import generate_hash
load_dotenv()

def get_web3() -> Web3:
    """Create n return connection to ETH Sepolia"""

    rpc_url = os.getenv("SEPOLIA_RPC_URL")
    if not rpc_url:
        raise ValueError("SEPOLIA_RPC_URL is not set in the environment variables.")
    
    web3 = Web3(Web3.HTTPProvider(rpc_url))
    if not web3.is_connected():
        raise ConnectionError("Failed to connect to the Ethereum Sepolia network.")
    
    return web3

def anchor_hash(hash_value: str) -> str:
    """
    Anchor a SHA-256 hash in data field of a Sepolia transaction.
    Returns:
        Transaction hash
    """
    private_key = os.getenv("PRIVATE_KEY")
    wallet_address = os.getenv("WALLET_ADDRESS")

    if not private_key:
        raise ValueError("PRIVATE_KEY is not set in the environment variables.")

    if not wallet_address:
        raise ValueError("WALLET_ADDRESS is not set in the environment variables.")

    web3 = get_web3()

    acc = web3.eth.account.from_key(private_key)
    if web3.to_checksum_address(wallet_address) != acc.address:
        raise ValueError("The provided PRIVATE_KEY does not match the WALLET_ADDRESS.")
    #fingerprint encoding as txn data
    payload = f"FACECHAIN:v1:{hash_value}".encode("utf-8")
    
    nonce = web3.eth.get_transaction_count(
        acc.address,
        "pending"
    )
    transaction = {
        "from": acc.address,
        "to": acc.address,
        "value": 0,
        "gas": 100000,
        "gasPrice": web3.eth.gas_price,
        "data": payload,
        "nonce": nonce,
        "chainId": web3.eth.chain_id,  # Sepolia chain ID - 11155111
    }

    signed_transaction = acc.sign_transaction(transaction)
    tx_hash = web3.eth.send_raw_transaction(signed_transaction.raw_transaction)
    return web3.to_hex(tx_hash)

def anchor_data(data: dict) -> dict:
    """
    Generate a hash from structured data and anchor it on Sepolia.
    """

    hash_value = generate_hash(data)

    transaction_hash = anchor_hash(hash_value)

    return {
        "hash": hash_value,
        "transaction_hash": transaction_hash
    }