from src.blockchain.anchor import get_web3

web3 = get_web3()

print("Connected:" , web3.is_connected())
print("Chain Id:", web3.eth.chain_id)
print("Current Block Number:", web3.eth.block_number)