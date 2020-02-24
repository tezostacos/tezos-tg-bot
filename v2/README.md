# Tezos Tacos Tipbot

Hello Tezos amigos! Tezos Tacos wanted to contribute in a fun way, so we made an open source Telegram Tipbot. It is decentralized using the KT18jF2bCerNgrkyk7qd1Bpk9gKnpPKJAvjB smart contract.

The bot interacts with the smart contract using pytezos. You can check all methods in the [Better Call Dev explorer](https://better-call.dev/main/KT18jF2bCerNgrkyk7qd1Bpk9gKnpPKJAvjB/operations) and research the code right there. To deposit XTZ to the Tezos Tacos Tipbot, use the "deposit" entrypoint with a string argument. All funds are stored in the smart contract with your Telegram username.

Example of cmd in CLI wallet:
```bash
tezos-client -A teznode.letzbake.com -S -P 443 transfer 0.1 from alias to KT18jF2bCerNgrkyk7qd1Bpk9gKnpPKJAvjB --entrypoint "deposit" --arg your_username -D
```

**Make sure that you sent your XTZ from the smart contract before changing your username in your Telegram profile**

Join us in our Baking Service Channel. We will giveaway 50 XTZ to the first users: https://t.me/tezostacosbaker

We also made the Tipbot an all-in-one data bot we think you will like `/tacos`

Thanks for your attention and happy tipping!