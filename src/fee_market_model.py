#!/usr/bin/env python3
"""fee_market_model.py — deterministic fee-market and transaction-pricing model.

Usage:
    python3 src/fee_market_model.py [--help]

Reads configs/scenarios.json and writes:
    outputs/derived/fee-market-results.json
    outputs/derived/scenario-matrix.json

Every number comes from the scenario inputs plus the pinned-code
constants in configs/scenarios.json (base fee level 256; minimum
escalation multiplier 128,000; minimum 32 transactions per ledger
(1,000 standalone); target 256; 20 ledgers in queue; minimum queue
size 2,000; at most 10 transactions per account; at most 10 retries;
25% replacement premium; minimum last-ledger buffer 2; normal load
factor 256; load step 1/4; maximum load factor 256,000,000;
privileged load cap 4x remote; series overflow guard 2^21). No live
node is involved, no timestamps are recorded, and no wall-clock time
is measured: re-running produces byte-identical outputs.

Pricing math (mirrors the pinned code, integer arithmetic throughout):
  - required open-ledger fee level: base level 256 while the open
    ledger holds at most `target` transactions; above target,
    multiplier * current^2 / target^2 (quadratic, TxQ.cpp:173-195).
  - escalation multiplier: median fee level of the last closed
    ledger, floored at 128,000 (TxQ.cpp:84-170).
  - fee level of a transaction: fee drops * 256 / base fee, where the
    base fee is 10 drops * (1 + number of signatures)
    (TxQ.cpp:39-66, Transactor.cpp:331-347).
  - load-scaled fee: fee * factor / 256, where the factor is the
    maximum of local and remote load, and a privileged submitter pays
    the remote factor while the local factor is below 4x remote
    (LoadFeeTrack.cpp:84-112).
  - minimum processing level when the queue is full: lowest queued
    fee level + 1, else 256 (TxQ.cpp:1778-1799).
  - slow consensus (timeLeap) halves the expected ledger size
    (TxQ.cpp:84-170).

Outcome rules (each is a direct application of a pinned rule, checked
in the order the code checks them):
  - fee below the local load-scaled fee: rejected locally (evicted).
  - LastLedgerSequence inside the 2-ledger buffer: cannot be held
    (evicted).
  - blocker with other queued transactions for the account: rejected
    (evicted).
  - replacement at or below 1.25x the old fee level: rejected
    (evicted).
  - account already at 10 queued transactions and not filling a
    sequence gap: rejected (evicted).
  - retries exhausted: dropped from the queue (stalled).
  - sequence gap ahead of the transaction: blocked (stalled).
  - series rescue: the summed fee levels of the queued series plus
    the new transaction cover the escalated series level (priced);
    otherwise the transaction queues (queued).
  - fee level at or above the required open-ledger level: priced.
  - queue full: admitted only if the fee level beats the lowest-fee
    account's average fee level, displacing its cheapest transaction
    (queued); otherwise rejected (evicted).
  - otherwise: queued below the open-ledger level.
Rounds: 1 for an outright decision; for a stalled run, the number of
ledgers the transaction waited (from the scenario input).
"""
import json
import sys
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parent.parent
PINNED_COMMIT = "0085a1ff885d6a446369cf73a4430f75af22be55"


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def required_level(target, multiplier, current):
    """TxQ::FeeMetrics::scaleFeeLevel, integer arithmetic."""
    if current <= target:
        return 256
    return multiplier * current * current // (target * target)


def fee_level_from_drops(fee_drops, signers, base_drops=10):
    """getFeeLevelPaid: fee * 256 / base fee, base fee grows per signer."""
    base_fee = base_drops * (1 + signers)
    return fee_drops * 256 // base_fee


def load_factor(privileged, local_factor, remote_factor):
    """scaleFeeLoad factor selection."""
    factor = max(local_factor, remote_factor)
    if privileged and factor > remote_factor and factor < 4 * remote_factor:
        factor = remote_factor
    return factor


def simulate_run(scenario, run, consts):
    p = run["params"]
    target = p["target"]
    if p.get("time_leap"):
        # Slow consensus halves the expected ledger size.
        target = max(p["expected_before"] * 50 // 100,
                     consts["minimum_txn_in_ledger"])
    multiplier = p["multiplier"]
    current = p["open_count"]
    required = required_level(target, multiplier, current)
    queue_full = p["queue_size"] >= p["queue_max"]
    min_processing = (p["lowest_queued_level"] + 1
                      if queue_full and p.get("lowest_queued_level") is not None
                      else 256)
    fee_level = p["fee_level"]
    if p.get("fee_drops") is not None:
        fee_level = fee_level_from_drops(
            p["fee_drops"], p.get("signers", 0), consts["base_fee_drops"])

    events = [{"round": ev["round"], "text": ev["text"]}
              for ev in run["events"]]

    outcome = None
    reason = None
    rounds = 1
    if p.get("fee_drops") is not None:
        eff = load_factor(p.get("privileged", False),
                          p.get("local_factor", 256),
                          p.get("remote_factor", 256))
        required_drops = consts["base_fee_drops"] * eff // 256
        if p["fee_drops"] < required_drops:
            outcome, reason = "evicted", "below_local_load_fee"
            events.append({"round": 1, "text": (
                f"fee {p['fee_drops']} drops is below the load-scaled "
                f"requirement {required_drops} drops (factor {eff}): "
                f"rejected locally")})
    if outcome is None and p.get("has_last_valid", True) \
            and not p.get("last_valid_ok", True):
        outcome, reason = "evicted", "last_ledger_sequence_inside_buffer"
        events.append({"round": 1, "text": (
            "LastLedgerSequence is inside the 2-ledger buffer: "
            "telCAN_NOT_QUEUE")})
    if outcome is None and p.get("is_blocker", False) \
            and p.get("account_queued", 0) > 0 \
            and not p.get("blocker_replaces_lone", False):
        outcome, reason = "evicted", "blocker_with_queued_transactions"
        events.append({"round": 1, "text": (
            f"blocker with {p['account_queued']} queued transactions for "
            f"the account: telCAN_NOT_QUEUE_BLOCKS")})
    if outcome is None and p.get("replacement_old_level") is not None:
        need = p["replacement_old_level"] * 125 // 100
        if fee_level <= need:
            outcome, reason = "evicted", "replacement_below_25pct_premium"
            events.append({"round": 1, "text": (
                f"replacement fee level {fee_level} is not above the "
                f"required {need} (old {p['replacement_old_level']} + 25%): "
                f"telCAN_NOT_QUEUE_FEE")})
    if outcome is None and p.get("account_queued", 0) >= 10 \
            and not p.get("gap_filling", False):
        outcome, reason = "evicted", "per_account_cap_reached"
        events.append({"round": 1, "text": (
            "account already has 10 queued transactions and the new one "
            "does not fill a sequence gap: telCAN_NOT_QUEUE_FULL")})
    if outcome is None and p.get("retries_left", 10) <= 0:
        outcome, reason = "stalled", "retries_exhausted"
        rounds = 10
        events.append({"round": 10, "text": (
            "10 retries used up without applying: dropped from the queue")})
    if outcome is None and not p.get("seq_ok", True):
        outcome, reason = "stalled", "blocked_behind_sequence_gap"
        rounds = p.get("ledgers_waited", 1)
        events.append({"round": rounds, "text": (
            "a lower-sequence transaction for the same account is ahead "
            "in the queue: this transaction cannot apply first")})
    if outcome is None and p.get("series_total") is not None:
        if p["series_total"] >= p["series_required"]:
            outcome, reason = "priced", "series_rescue_clears_account_queue"
            events.append({"round": 1, "text": (
                f"summed series fee level {p['series_total']} covers the "
                f"escalated series requirement {p['series_required']}: "
                f"the whole account queue clears into the open ledger")})
        else:
            outcome, reason = "queued", "series_rescue_fee_insufficient"
            events.append({"round": 1, "text": (
                f"summed series fee level {p['series_total']} is below the "
                f"escalated series requirement {p['series_required']}: "
                f"queues instead of clearing")})
    if outcome is None and fee_level >= required:
        outcome, reason = "priced", "at_or_above_required_open_ledger_level"
        events.append({"round": 1, "text": (
            f"fee level {fee_level} is at or above the required level "
            f"{required}: applies to the open ledger")})
    if outcome is None and queue_full:
        avg = p.get("lowest_account_avg")
        if avg is not None and fee_level > avg:
            outcome, reason = "queued", "admitted_displacing_cheapest"
            events.append({"round": 1, "text": (
                f"queue is full but fee level {fee_level} beats the "
                f"lowest-fee account average {avg}: admitted, cheapest "
                f"transaction of that account is dropped")})
        else:
            outcome, reason = "evicted", "below_lowest_account_average_when_full"
            events.append({"round": 1, "text": (
                f"queue is full and fee level {fee_level} does not beat "
                f"the lowest-fee account average {avg}: "
                f"telCAN_NOT_QUEUE_FULL")})
    if outcome is None:
        outcome, reason = "queued", "below_open_ledger_level_queued"
        events.append({"round": 1, "text": (
            f"fee level {fee_level} is below the required level "
            f"{required}: held in the queue for a later ledger")})

    return {
        "label": run["label"],
        "title": run["title"],
        "params": p,
        "target": target,
        "multiplier": multiplier,
        "open_count": current,
        "required_level": required,
        "min_processing_level": min_processing,
        "fee_level": fee_level,
        "queue_size": p["queue_size"],
        "queue_max": p["queue_max"],
        "queue_full": queue_full,
        "outcome": outcome,
        "reason": reason,
        "rounds": rounds,
        "events": events,
    }


def main():
    if "--help" in sys.argv[1:]:
        print(__doc__.strip())
        print("\nusage: python3 src/fee_market_model.py [--help]")
        return 0
    sc = load_json(PACK_ROOT / "configs" / "scenarios.json")
    consts = sc["constants"]
    assert sc.get("pinned_commit") == PINNED_COMMIT, "scenarios pinned_commit mismatch"
    assert sc.get("schema_version") == 1, "scenarios schema_version != 1"

    results_scenarios = []
    matrix_rows = []
    totals = {"scenarios": 0, "runs": 0, "priced": 0, "queued": 0,
              "evicted": 0, "stalled": 0}
    for scenario in sc["scenarios"]:
        runs = [simulate_run(scenario, run, consts)
                for run in scenario["runs"]]
        results_scenarios.append({
            "id": scenario["id"],
            "title": scenario["title"],
            "runs": runs,
        })
        totals["scenarios"] += 1
        for run in runs:
            totals["runs"] += 1
            totals[run["outcome"]] += 1
            matrix_rows.append({
                "scenario": scenario["id"],
                "run": run["label"],
                "target": run["target"],
                "multiplier": run["multiplier"],
                "open_count": run["open_count"],
                "required_level": run["required_level"],
                "min_processing_level": run["min_processing_level"],
                "fee_level": run["fee_level"],
                "queue_size": run["queue_size"],
                "queue_max": run["queue_max"],
                "outcome": run["outcome"],
                "reason": run["reason"],
                "rounds": run["rounds"],
            })

    threshold_table = []
    for target, multiplier, current in (
            (32, 128000, 32), (32, 128000, 33), (32, 128000, 40),
            (256, 281600, 256), (256, 281600, 300), (256, 128000, 512),
            (1000, 128000, 1000)):
        req = required_level(target, multiplier, current)
        threshold_table.append({
            "target": target,
            "multiplier": multiplier,
            "open_count": current,
            "required_level": req,
            "required_drops_at_10_drop_base": req * 10 // 256,
            "multiple_of_median": (req / multiplier) if multiplier else None,
        })

    limits_table = [
        {"item": "base fee level", "value": consts["base_level"], "unit": "level"},
        {"item": "minimum escalation multiplier", "value": consts["minimum_escalation_multiplier"], "unit": "level"},
        {"item": "minimum transactions per ledger", "value": consts["minimum_txn_in_ledger"], "unit": "transactions"},
        {"item": "minimum transactions per ledger (standalone)", "value": consts["minimum_txn_in_ledger_standalone"], "unit": "transactions"},
        {"item": "target transactions per ledger", "value": consts["target_txn_in_ledger"], "unit": "transactions"},
        {"item": "ledgers in queue", "value": consts["ledgers_in_queue"], "unit": "ledgers"},
        {"item": "minimum queue size", "value": consts["queue_size_min"], "unit": "transactions"},
        {"item": "maximum transactions per account", "value": consts["maximum_txn_per_account"], "unit": "transactions"},
        {"item": "maximum retries", "value": consts["retries_allowed"], "unit": "attempts"},
        {"item": "replacement premium", "value": consts["retry_sequence_percent"], "unit": "percent"},
        {"item": "minimum last-ledger buffer", "value": consts["minimum_last_ledger_buffer"], "unit": "ledgers"},
        {"item": "normal load factor", "value": consts["load_normal_fee"], "unit": "factor"},
        {"item": "load step", "value": "1/4", "unit": "fraction"},
        {"item": "maximum load factor", "value": consts["load_fee_max"], "unit": "factor"},
        {"item": "privileged load cap", "value": consts["privileged_load_cap_multiple"], "unit": "x remote factor"},
        {"item": "series overflow guard", "value": consts["series_overflow_guard"], "unit": "transactions"},
        {"item": "queue-full threshold", "value": 100, "unit": "percent"},
        {"item": "penalty threshold", "value": 95, "unit": "percent"},
        {"item": "reference base fee", "value": consts["base_fee_drops"], "unit": "drops"},
    ]

    results = {
        "pack": "Fee-Market and Transaction-Pricing in postfiatd",
        "pinned_commit": PINNED_COMMIT,
        "constants": consts,
        "scenarios": results_scenarios,
        "totals": totals,
        "threshold_table": threshold_table,
        "limits_table": limits_table,
    }
    matrix = {"rows": matrix_rows, "totals": totals}

    outdir = PACK_ROOT / "outputs" / "derived"
    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / "fee-market-results.json", "w") as fh:
        json.dump(results, fh, indent=1, sort_keys=True)
        fh.write("\n")
    with open(outdir / "scenario-matrix.json", "w") as fh:
        json.dump(matrix, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"simulator: {totals['scenarios']} scenarios, {totals['runs']} runs")
    print(f"simulator: priced {totals['priced']}, queued {totals['queued']}, "
          f"evicted {totals['evicted']}, stalled {totals['stalled']}")
    print("simulator: wrote outputs/derived/fee-market-results.json")
    print("simulator: wrote outputs/derived/scenario-matrix.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
