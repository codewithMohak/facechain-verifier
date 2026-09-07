# Facechain-verifier

## Blockchain anchoring

The verification pipeline can anchor its generated verification record on
Ethereum Sepolia. Copy `.env.example` to `.env`, then set:

```text
SEPOLIA_RPC_URL=https://your-sepolia-rpc-url
PRIVATE_KEY=your-wallet-private-key
WALLET_ADDRESS=0xYourWalletAddress
BLOCKCHAIN_ANCHOR_ENABLED=true
```

The wallet must hold enough Sepolia ETH to pay for the transaction. The
application stores the SHA-256 record hash and transaction hash in
`data/verification_metadata.json` under `blockchain`.

With `BLOCKCHAIN_ANCHOR_ENABLED=false` or unset, face verification still runs
without submitting a transaction.
