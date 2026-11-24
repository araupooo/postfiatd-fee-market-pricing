# Citations

Public documentation consulted for the SPECIFIED rules, with verbatim
quotes. Accessed 24 Nov 2026. Each entry notes whether the code
agrees, and where it diverges the pack follows the code.

## S-01 — Transaction fees are destroyed, not paid to anyone

Source: https://xrpl.org/docs/references/protocol/transactions/transaction-cost
(XRPL.org transaction-cost documentation.)

> "The transaction cost is not paid to any party: the XRP is irrevocably destroyed."

Cross-check: agrees with the code's framing — the fee is a cost to
destroy, never a payment to a validator or to the queue; no code path
in TxQ or LoadFeeTrack pays a fee to anyone. Rule R-39.

## S-02 — Admin connections bypass load scaling

Source: https://xrpl.org/docs/references/protocol/transactions/transaction-cost
(same page as S-01.)

> "If you submit a transaction through an admin connection, the server applies and relays the transaction as long as the transaction meets the un-scaled minimum transaction cost."

Cross-check: agrees with the code — `scaleFeeLoad` is applied with
the privileged flag for unlimited connections
(`LoadFeeTrack.cpp:84-112`, E36), and the privileged cap only bites
while the local factor is below four times remote. Rule R-40.

## S-03 — A fee must meet a majority of servers' requirements

Source: https://xrpl.org/docs/references/protocol/transactions/transaction-cost
(same page as S-01.)

> "A transaction is very unlikely to survive the consensus process unless its Fee value meets the requirements of a majority of servers."

Cross-check: agrees with the code's design — each server tracks its
own local, remote, and cluster load factors (`LoadFeeTrack.h:95-120`,
E32), so the effective threshold differs per server. Rule R-41.

## S-04 — Two thresholds under fee escalation

Source: https://xrpl.org/docs/references/protocol/transactions/transaction-cost
(same page as S-01.)

> "When the FeeEscalation amendment is enabled, there are two thresholds for the transaction cost:"

Cross-check: agrees with the code — the load-based threshold
(`scaleFeeLoad`, E36) gates whether a server applies or relays at
all, and the open-ledger threshold (`scaleFeeLevel`, E11) gates
whether the transaction goes straight into the open ledger or into
the queue. Rule R-42.
