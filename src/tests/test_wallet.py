import os
from dotenv import load_dotenv
from src.blockchain.anchor import get_web3

load_dotenv()
web3 = get_web3()
wallett_address = os.getenv("WALLET_ADDRESS")

if not wallett_address:
    raise ValueError("WALLET_ADDRESS is not set in the environment variables.")

wallet_address = web3.to_checksum_address(wallett_address)

balance_wei = web3.eth.get_balance(wallet_address)
balance_eth = web3.from_wei(balance_wei, "ether")

print("wallet: ", wallet_address)
print("sepolia balance: ", balance_eth, "ETH")