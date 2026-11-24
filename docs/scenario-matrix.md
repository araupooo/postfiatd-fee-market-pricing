# Scenario matrix

Deterministic outputs of `src/fee_market_model.py` on
`configs/scenarios.json`. `required_level` is the open-ledger fee
level a transaction must pay to price in: 256 at or below the target,
otherwise multiplier * open_count^2 / target^2 (integer arithmetic,
as in `TxQ.cpp:173-195`). `min_processing_level` is the lowest queued
fee level plus one when the queue is full, else 256. priced: the
transaction applies to the open ledger. queued: held in the queue for
a later ledger. evicted: rejected from the queue. stalled: queued but
blocked or dropped without applying. Rounds: 1 for an outright
decision; for a stalled run, the number of ledgers the transaction
waited.

| Scenario | Run | Target | Multiplier | Open count | Required level | Min processing level | Fee level | Queue | Outcome | Reason | Rounds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S-01 | A | 32 | 128000 | 40 | 200000 | 256 | 256 | 0/2000 | queued | below_open_ledger_level_queued | 1 |
| S-01 | B | 32 | 128000 | 40 | 200000 | 256 | 250000 | 0/2000 | priced | at_or_above_required_open_ledger_level | 1 |
| S-02 | A | 256 | 281600 | 300 | 386718 | 256 | 256 | 0/2000 | queued | below_open_ledger_level_queued | 1 |
| S-02 | B | 256 | 281600 | 300 | 386718 | 256 | 500000 | 0/2000 | priced | at_or_above_required_open_ledger_level | 1 |
| S-03 | A | 32 | 128000 | 40 | 200000 | 257 | 256 | 2000/2000 | evicted | below_lowest_account_average_when_full | 1 |
| S-03 | B | 32 | 128000 | 40 | 200000 | 257 | 512 | 2000/2000 | queued | admitted_displacing_cheapest | 1 |
| S-04 | A | 32 | 128000 | 10 | 256 | 256 | 512 | 100/2000 | evicted | per_account_cap_reached | 1 |
| S-05 | A | 32 | 128000 | 40 | 200000 | 256 | 100000 | 0/2000 | stalled | blocked_behind_sequence_gap | 3 |
| S-05 | B | 32 | 128000 | 40 | 200000 | 256 | 1000000 | 0/2000 | priced | series_rescue_clears_account_queue | 1 |
| S-06 | A | 32 | 128000 | 10 | 256 | 256 | 512 | 100/2000 | evicted | blocker_with_queued_transactions | 1 |
| S-07 | A | 32 | 128000 | 10 | 256 | 256 | 614 | 100/2000 | evicted | replacement_below_25pct_premium | 1 |
| S-08 | A | 32 | 128000 | 10 | 256 | 256 | 512 | 100/2000 | evicted | last_ledger_sequence_inside_buffer | 1 |
| S-08 | B | 32 | 128000 | 10 | 256 | 256 | 512 | 100/2000 | stalled | retries_exhausted | 10 |
| S-09 | A | 32 | 128000 | 10 | 256 | 256 | 256 | 0/2000 | priced | at_or_above_required_open_ledger_level | 1 |
| S-10 | A | 32 | 128000 | 40 | 200000 | 256 | 1536 | 0/2000 | queued | below_open_ledger_level_queued | 1 |
| S-11 | A | 32 | 128000 | 40 | 200000 | 401 | 384 | 2000/2000 | evicted | below_lowest_account_average_when_full | 1 |
| S-12 | A | 250 | 128000 | 300 | 184320 | 256 | 150000 | 0/2000 | queued | below_open_ledger_level_queued | 1 |
| S-13 | A | 32 | 128000 | 33 | 136125 | 256 | 140000 | 0/2000 | priced | at_or_above_required_open_ledger_level | 1 |

Totals: 13 scenarios, 18 runs — priced 5, queued 5, evicted 6, stalled 2.

## Threshold table

Minimum fee level to enter the open ledger at a given load (base fee 10 drops):

| Target | Multiplier | Open count | Required level | Required drops | Multiple of median |
| --- | --- | --- | --- | --- | --- |
| 32 | 128000 | 32 | 256 | 10 | 0.002 |
| 32 | 128000 | 33 | 136125 | 5317 | 1.0634765625 |
| 32 | 128000 | 40 | 200000 | 7812 | 1.5625 |
| 256 | 281600 | 256 | 256 | 10 | 0.0009090909090909091 |
| 256 | 281600 | 300 | 386718 | 15106 | 1.3732883522727273 |
| 256 | 128000 | 512 | 512000 | 20000 | 4.0 |
| 1000 | 128000 | 1000 | 256 | 10 | 0.002 |

## Limits table

| Item | Value | Unit |
| --- | --- | --- |
| base fee level | 256 | level |
| minimum escalation multiplier | 128000 | level |
| minimum transactions per ledger | 32 | transactions |
| minimum transactions per ledger (standalone) | 1000 | transactions |
| target transactions per ledger | 256 | transactions |
| ledgers in queue | 20 | ledgers |
| minimum queue size | 2000 | transactions |
| maximum transactions per account | 10 | transactions |
| maximum retries | 10 | attempts |
| replacement premium | 25 | percent |
| minimum last-ledger buffer | 2 | ledgers |
| normal load factor | 256 | factor |
| load step | 1/4 | fraction |
| maximum load factor | 256000000 | factor |
| privileged load cap | 4 | x remote factor |
| series overflow guard | 2097152 | transactions |
| queue-full threshold | 100 | percent |
| penalty threshold | 95 | percent |
| reference base fee | 10 | drops |

