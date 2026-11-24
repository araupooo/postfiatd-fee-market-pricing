# Operator decision memo

How to price a transaction and survive a fee spike on postfiatd, from
the pinned fee-market code.

## The pricing rule in one paragraph

A transaction's fee level is its fee in drops times 256 divided by its
base fee (10 drops for a single-signed reference transaction, 10 drops
per extra signer). While the open ledger holds at most the target
number of transactions (256 by default), fee level 256 — 10 drops —
gets in. Above the target, the required level is the last ledger's
median fee level times the square of the open-ledger count over the
square of the target. The median is floored at 128,000, so the first
escalated fee on a cold ledger is already about 136,125 (roughly
5,317 drops). At twice the target the required level is four times
the median; at four times the target, sixteen times.

## What to do

1. **Read the `fee` command before submitting.** It reports the
   current open-ledger level and the minimum queue level in drops.
   The value is instantaneous: re-read it immediately before
   submitting, and expect it to move during a flood.
2. **Pay by fee level, not by drops.** A 3-signature transaction
   paying 60 drops has fee level 384; a single-signed transaction
   paying 20 drops has level 512 and queues ahead of it. Compute
   level = drops * 256 / (10 * (1 + signers)).
3. **During a spike, either pay above the open-ledger level or queue
   and wait.** Below the required level a transaction is held in the
   queue and applied to a later ledger when the required level drops
   back to 256. Queued transactions are drained highest fee first.
4. **Mind the queue maximum.** The queue holds the larger of
   expected-ledgers-times-20 and 2,000 transactions. When it is full,
   a newcomer is admitted only if its fee level beats the lowest-fee
   account's average fee level — and the cheapest transaction of that
   account is dropped. Keep each account's queued transactions at
   similar fee levels so one cheap transaction does not expose a dear
   one.
5. **Submit sequences in order.** A high-fee transaction behind a
   low-fee predecessor stalls. If an account's queue is stuck, one
   transaction paying enough to cover the escalated series level for
   the whole series rescues the account — but the sum has to cover
   the quadratic series total, which grows fast.
6. **Replacement costs 25% more.** Replacing a queued transaction
   needs a fee level strictly above the old level plus 25%.
7. **Set an adequate LastLedgerSequence.** It must be at least 2
   ledgers past the open ledger to queue at all, and an expired
   transaction marks the account: its later transactions get dropped
   when the queue is 95% full.
8. **Expect fee spikes during slow consensus.** A slow ledger halves
   the expected ledger size, which raises the required level for the
   same load — in the modelled case from 46,080 to 184,320.
9. **Do not trust FeeEscalation.md's numbers.** It says minimum 5
   and target 50; the code says 32 and 256. It says the fee level
   "increases exponentially"; the code is quadratic. Price from the
   code and the `fee` command.

## What not to rely on

- The queue does not guarantee admission: at most 10 transactions
  per account, and a full queue rejects anything that does not beat
  the lowest-fee account's average.
- The load fee is per-server: a transaction meeting one server's load
  fee may be dropped by others. Pay above what a majority of servers
  would require.
- Equal fee levels order by transaction ID XOR the parent hash, which
  changes every ledger. Pay a distinct fee level to order
  deterministically.
