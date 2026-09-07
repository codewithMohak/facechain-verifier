import os
from dotenv import load_dotenv
from web3 import Web3

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