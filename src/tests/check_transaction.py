from web3.exceptions import TransactionNotFound

from src.blockchain.anchor import get_web3


transaction_hash = "0x7bccb3652d7f164d7bca8d1cf58488368edc2420cc117aa16a5e7df29691e4e2"

web3 = get_web3()

try:
    receipt = web3.eth.get_transaction_receipt(transaction_hash)

    print("Transaction found!")
    print("Status:", receipt["status"])
    print("Block number:", receipt["blockNumber"])

except TransactionNotFound:
    print("Transaction is not confirmed yet.")
    print("It may still be pending or may have been dropped.")