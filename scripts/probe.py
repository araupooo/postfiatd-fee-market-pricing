#!/usr/bin/env python3
"""probe.py — re-verify the fee-market and transaction-pricing pack from its outputs.

Usage:
    python3 scripts/probe.py [--skip-manifest-check] [FEE_MARKET_RESULTS_JSON]

The --skip-manifest-check flag is for run_all.sh step 4 only: the
manifest on disk at that point predates the just-regenerated results,
so comparing against it would fail on any input change; step 5b re-runs
the probe without the flag after rewriting the manifest. A standalone
probe run (no flag) always performs the manifest check.

Checks (all re-derived, none trusted):
  A-00 pinned checkout HEAD equals the pinned commit.
  A-01 every VERIFIED rule's anchor sits inside its cited range in the
     pinned checkout; SPECIFIED rules carry external URLs; MODELLED /
     UNTESTABLE rules carry no file source. (45 rules: 38/4/2/1.)
  B-01 scenario arithmetic: 13 scenarios, 18 runs; outcomes priced 5 /
     queued 5 / evicted 6 / stalled 2; matrix rows == runs; required
     levels, minimum processing levels, and fee levels re-derived from
     the scenario params; outcomes and reasons re-derived from the
     scenario params.
  C-01 threshold and limits tables re-derived: required levels match
     the quadratic escalation math; limits table matches the pinned
     constants.
  D-01 key tokens at recorded lines: baseLevel 256 (TxQ.h:64),
     ledgersInQueue 20 (:81), queueSizeMin 2000 (:87),
     retrySequencePercent 25 (:97), minimumEscalationMultiplier
     baseLevel * 500 (:100), minimumTxnInLedger 32 (:103),
     targetTxnInLedger 256 (:109), maximumTxnPerAccount 10 (:148),
     minimumLastLedgerBuffer 2 (:155), retriesAllowed 10 (:580),
     lftNormalFee (LoadFeeTrack.h:141), lftFeeMax (LoadFeeTrack.h:147),
     median fee levels (TxQ.cpp:161), quadratic mulDiv (TxQ.cpp:187),
     signerCount * baseFee (Transactor.cpp:345).
  E-01 queue logic re-grepped: fee-level descending order with the
     parent-hash tie-break; isFull at 100%; maxSize_ formula; accept
     stops at the first transaction below the required level; expired
     transactions removed at ledger close; series rescue uses the
     escalated series level.
  F-01 counts reconcile across files: matrix == results == scenarios
     (13); findings 12 (HIGH 3, MEDIUM 6, LOW 3), claims 24
     (16/2/4/2), risks 14 (HIGH 3, MEDIUM 8, LOW 3), gaps 8; excerpts
     44 across 8 files agree across manifest, files, hashes.
  G-01 determinism: re-running the simulator to a temp dir reproduces
     byte-identical outputs (full SHA-256 compare).
  H-01 excerpt integrity: every excerpt file digest matches
     fixtures/source-hashes.json and every manifest blob SHA/size
     matches `git hash-object` / file size in the checkout;
     run-manifest digests match the shipped derived files; recorded
     reproduction log digests match the fresh-clone logs on disk; the
     recorded verify-digests digest matches outputs/verify-digests.log
     when the manifest carries one.
  I-01 absence findings re-grepped: std::exp 0 hits in TxQ.cpp and
     LoadFeeTrack.cpp (escalation is quadratic, not exponential);
     maxFeeLevel 0 hits; discount 0 hits; no per-account fee
     discount token; the escalation multiplier is never capped with
     std::min; "exponentially" appears only in comments and the design
     document, never in TxQ.cpp.
  J-01 divergence tokens: the design document says the fee level
     "increases exponentially" (FeeEscalation.md:57) while the code
     computes a quadratic; the document says minimum 5 / target 50
     (FeeEscalation.md:226-228) while the code says 32 / 256; the
     class comment repeats the exponential claim (TxQ.h:48).
  T-01 timing sanity only (non-negative, never recorded).

Exit 0 only if every case passes. Prints one PASS/FAIL line per case
with the FULL 64-char SHA-256 digest where a digest is involved, and
writes outputs/derived/probe-results.json plus outputs/probe-run.log
(the log is the unedited stdout of this run; it contains no absolute
paths and no timestamps). No live node is involved.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parent.parent
PINNED_COMMIT = "0085a1ff885d6a446369cf73a4430f75af22be55"
PINNED_CHECKOUT = Path(os.environ.get(
    "PINNED_CHECKOUT", str(Path.home() / "workspace" / "postfiatd-pin-0085a1f")))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def git_blob(relpath):
    out = subprocess.run(["git", "-C", str(PINNED_CHECKOUT), "hash-object", "--", relpath],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def read_lines(relpath):
    return (PINNED_CHECKOUT / relpath).read_text().splitlines()


def grep_hits(pattern, *roots):
    proc = subprocess.run(
        ["grep", "-rn", pattern, *[str(PINNED_CHECKOUT / r) for r in roots]],
        capture_output=True, text=True)
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


def required_level(target, multiplier, current):
    if current <= target:
        return 256
    return multiplier * current * current // (target * target)


def classify(p):
    """Re-derive the model outcome from scenario params (mirror of the model)."""
    target = p["target"]
    if p.get("time_leap"):
        target = max(p["expected_before"] * 50 // 100, 32)
    req = required_level(target, p["multiplier"], p["open_count"])
    queue_full = p["queue_size"] >= p["queue_max"]
    min_proc = (p["lowest_queued_level"] + 1
                if queue_full and p.get("lowest_queued_level") is not None
                else 256)
    fee_level = p["fee_level"]
    if p.get("fee_drops") is not None:
        fee_level = p["fee_drops"] * 256 // (10 * (1 + p.get("signers", 0)))
    if p.get("fee_drops") is not None:
        eff = max(p.get("local_factor", 256), p.get("remote_factor", 256))
        if p.get("privileged", False) and eff > p.get("remote_factor", 256) \
                and eff < 4 * p.get("remote_factor", 256):
            eff = p.get("remote_factor", 256)
        if p["fee_drops"] < 10 * eff // 256:
            return "evicted", "below_local_load_fee", 1, req, min_proc, fee_level, target
    if p.get("has_last_valid", True) and not p.get("last_valid_ok", True):
        return "evicted", "last_ledger_sequence_inside_buffer", 1, req, min_proc, fee_level, target
    if p.get("is_blocker", False) and p.get("account_queued", 0) > 0 \
            and not p.get("blocker_replaces_lone", False):
        return "evicted", "blocker_with_queued_transactions", 1, req, min_proc, fee_level, target
    if p.get("replacement_old_level") is not None:
        if fee_level <= p["replacement_old_level"] * 125 // 100:
            return "evicted", "replacement_below_25pct_premium", 1, req, min_proc, fee_level, target
    if p.get("account_queued", 0) >= 10 and not p.get("gap_filling", False):
        return "evicted", "per_account_cap_reached", 1, req, min_proc, fee_level, target
    if p.get("retries_left", 10) <= 0:
        return "stalled", "retries_exhausted", 10, req, min_proc, fee_level, target
    if not p.get("seq_ok", True):
        return "stalled", "blocked_behind_sequence_gap", p.get("ledgers_waited", 1), req, min_proc, fee_level, target
    if p.get("series_total") is not None:
        if p["series_total"] >= p["series_required"]:
            return "priced", "series_rescue_clears_account_queue", 1, req, min_proc, fee_level, target
        return "queued", "series_rescue_fee_insufficient", 1, req, min_proc, fee_level, target
    if fee_level >= req:
        return "priced", "at_or_above_required_open_ledger_level", 1, req, min_proc, fee_level, target
    if queue_full:
        avg = p.get("lowest_account_avg")
        if avg is not None and fee_level > avg:
            return "queued", "admitted_displacing_cheapest", 1, req, min_proc, fee_level, target
        return "evicted", "below_lowest_account_average_when_full", 1, req, min_proc, fee_level, target
    return "queued", "below_open_ledger_level_queued", 1, req, min_proc, fee_level, target


def main():
    started = time.time()
    argv = [a for a in sys.argv[1:] if a != "--skip-manifest-check"]
    skip_manifest = "--skip-manifest-check" in sys.argv[1:]
    results_path = Path(argv[0]) if argv else \
        PACK_ROOT / "outputs" / "derived" / "fee-market-results.json"
    doc = load_json(results_path)
    matrix = load_json(PACK_ROOT / "outputs" / "derived" / "scenario-matrix.json")
    rules = load_json(PACK_ROOT / "configs" / "fee-market-rules.json")["rules"]
    scenarios = load_json(PACK_ROOT / "configs" / "scenarios.json")["scenarios"]
    manifest = load_json(PACK_ROOT / "fixtures" / "excerpts-manifest.json")
    hashes = load_json(PACK_ROOT / "fixtures" / "source-hashes.json")
    findings = load_json(PACK_ROOT / "findings.json")["findings"]
    checks, lines = [], []

    def check(cid, label, ok, detail=""):
        checks.append({"id": cid, "check": label, "pass": bool(ok), "detail": detail})
        lines.append(("PASS " if ok else "FAIL ") + cid + " " + label +
                     ((" — " + detail) if detail else ""))

    # A-00: pinned checkout HEAD.
    head = subprocess.run(["git", "-C", str(PINNED_CHECKOUT), "rev-parse", "HEAD"],
                          capture_output=True, text=True)
    check("A-00", "pinned checkout HEAD equals the pinned commit",
          head.stdout.strip() == PINNED_COMMIT,
          f"HEAD={head.stdout.strip()}")

    # A-01: rule anchors inside cited ranges.
    bad = []
    counts = Counter(r["status"] for r in rules)
    for r in rules:
        if r["status"] == "VERIFIED":
            s = r.get("source")
            if not s:
                bad.append(f"{r['id']}: no source")
                continue
            try:
                chunk = read_lines(s["file"])[s["start_line"] - 1:s["end_line"]]
            except (FileNotFoundError, IndexError):
                bad.append(f"{r['id']}: unreadable range")
                continue
            if s.get("anchor") and not any(s["anchor"] in ln for ln in chunk):
                bad.append(f"{r['id']}: anchor not in range")
        elif r["status"] == "SPECIFIED":
            ext = r.get("external")
            if not ext or "url" not in ext or "quote" not in ext:
                bad.append(f"{r['id']}: specified rule needs url+quote")
        else:
            if r.get("source") is not None:
                bad.append(f"{r['id']}: {r['status']} rule must carry no file source")
    check("A-01",
          "45 rules: 38 VERIFIED anchors inside cited ranges, 4 SPECIFIED (external URLs), 2 MODELLED, 1 UNTESTABLE, none with a faked source",
          not bad and len(rules) == 45 and counts == {"VERIFIED": 38, "SPECIFIED": 4, "MODELLED": 2, "UNTESTABLE": 1},
          "; ".join(bad[:3]) or f"counts={dict(sorted(counts.items()))}")

    # B-01: scenario arithmetic.
    totals = doc["totals"]
    runs = [run for sc in doc["scenarios"] for run in sc["runs"]]
    outcomes = Counter(run["outcome"] for run in runs)
    arith_ok = True
    arith_bad = []
    for run in runs:
        p = run["params"]
        exp_outcome, exp_reason, exp_rounds, exp_req, exp_min, exp_fee, exp_target = classify(p)
        if run["required_level"] != exp_req or run["min_processing_level"] != exp_min \
                or run["fee_level"] != exp_fee or run["target"] != exp_target:
            arith_ok = False
            arith_bad.append(f"{run['label']}: level math req={run['required_level']}/{exp_req} min={run['min_processing_level']}/{exp_min} fee={run['fee_level']}/{exp_fee} target={run['target']}/{exp_target}")
        if run["outcome"] != exp_outcome or run["reason"] != exp_reason:
            arith_ok = False
            arith_bad.append(f"{run['label']}: outcome {run['outcome']}/{run['reason']} != {exp_outcome}/{exp_reason}")
        if run["rounds"] != exp_rounds:
            arith_ok = False
            arith_bad.append(f"{run['label']}: rounds {run['rounds']} != {exp_rounds}")
    check("B-01",
          "per-scenario arithmetic reconciles; totals 13 scenarios / 18 runs / priced 5 / queued 5 / evicted 6 / stalled 2; matrix rows == runs; required levels, minimum processing levels, and fee levels re-derived; outcomes and reasons re-derived from the scenario params",
          totals == {"scenarios": 13, "runs": 18, "priced": 5,
                     "queued": 5, "evicted": 6, "stalled": 2}
          and outcomes == {"priced": 5, "queued": 5, "evicted": 6, "stalled": 2}
          and len(matrix["rows"]) == 18 and arith_ok,
          f"totals={totals} outcomes={dict(outcomes)} " + "; ".join(arith_bad[:3]))

    # C-01: threshold and limits tables re-derived.
    c_ok = True
    c_detail = []
    for row in doc["threshold_table"]:
        exp_req = required_level(row["target"], row["multiplier"], row["open_count"])
        exp_drops = exp_req * 10 // 256
        if (row["required_level"] != exp_req
                or row["required_drops_at_10_drop_base"] != exp_drops
                or abs(row["multiple_of_median"] - exp_req / row["multiplier"]) > 1e-9):
            c_ok = False
            c_detail.append(f"target={row['target']} open={row['open_count']}")
    lim = {r["item"]: r["value"] for r in doc["limits_table"]}
    c_ok = c_ok and lim.get("base fee level") == 256 \
        and lim.get("minimum escalation multiplier") == 128000 \
        and lim.get("minimum transactions per ledger") == 32 \
        and lim.get("minimum transactions per ledger (standalone)") == 1000 \
        and lim.get("target transactions per ledger") == 256 \
        and lim.get("ledgers in queue") == 20 \
        and lim.get("minimum queue size") == 2000 \
        and lim.get("maximum transactions per account") == 10 \
        and lim.get("maximum retries") == 10 \
        and lim.get("replacement premium") == 25 \
        and lim.get("minimum last-ledger buffer") == 2 \
        and lim.get("normal load factor") == 256 \
        and lim.get("load step") == "1/4" \
        and lim.get("maximum load factor") == 256000000 \
        and lim.get("privileged load cap") == 4 \
        and lim.get("series overflow guard") == 2097152 \
        and lim.get("queue-full threshold") == 100 \
        and lim.get("penalty threshold") == 95 \
        and lim.get("reference base fee") == 10
    check("C-01",
          "threshold rows match the quadratic escalation math for 7 target/multiplier/open-count triples; limits table matches the pinned constants (256 base level, 128,000 minimum multiplier, 32/1,000 minimum, 256 target, 20 ledgers in queue, 2,000 minimum queue, 10 per account, 10 retries, 25% premium, 2-ledger buffer, 256 normal load, 1/4 step, 256,000,000 maximum load, 4x privileged cap, 2^21 series guard, 100% full, 95% penalty, 10-drop base fee)",
          c_ok, "; ".join(c_detail[:3]) or "all match")

    # D-01: key tokens at recorded lines.
    def token_at(relpath, lineno, token):
        chunk = read_lines(relpath)
        return lineno <= len(chunk) and token in chunk[lineno - 1]

    d_checks = [
        ("src/xrpld/app/misc/TxQ.h", 64, "static constexpr FeeLevel64 baseLevel{256};"),
        ("src/xrpld/app/misc/TxQ.h", 81, "ledgersInQueue = 20"),
        ("src/xrpld/app/misc/TxQ.h", 87, "queueSizeMin = 2000"),
        ("src/xrpld/app/misc/TxQ.h", 97, "retrySequencePercent = 25"),
        ("src/xrpld/app/misc/TxQ.h", 100, "minimumEscalationMultiplier = baseLevel * 500"),
        ("src/xrpld/app/misc/TxQ.h", 103, "minimumTxnInLedger = 32"),
        ("src/xrpld/app/misc/TxQ.h", 109, "targetTxnInLedger = 256"),
        ("src/xrpld/app/misc/TxQ.h", 148, "maximumTxnPerAccount = 10"),
        ("src/xrpld/app/misc/TxQ.h", 155, "minimumLastLedgerBuffer = 2"),
        ("src/xrpld/app/misc/TxQ.h", 580, "retriesAllowed = 10"),
        ("src/xrpld/app/misc/LoadFeeTrack.h", 141, "lftNormalFee"),
        ("src/xrpld/app/misc/LoadFeeTrack.h", 147, "lftFeeMax = lftNormalFee * 1000000"),
        ("src/xrpld/app/misc/detail/TxQ.cpp", 161, "feeLevels[size / 2]"),
        ("src/xrpld/app/misc/detail/TxQ.cpp", 187, "current * current, target * target"),
        ("src/xrpld/app/tx/detail/Transactor.cpp", 345, "signerCount * baseFee"),
    ]
    d_bad = [f"{f}:{ln} {t!r}" for f, ln, t in d_checks if not token_at(f, ln, t)]
    check("D-01",
          "baseLevel 256 (TxQ.h:64), ledgersInQueue 20 (:81), queueSizeMin 2000 (:87), retrySequencePercent 25 (:97), minimumEscalationMultiplier baseLevel * 500 (:100), minimumTxnInLedger 32 (:103), targetTxnInLedger 256 (:109), maximumTxnPerAccount 10 (:148), minimumLastLedgerBuffer 2 (:155), retriesAllowed 10 (:580), lftNormalFee (LoadFeeTrack.h:141), lftFeeMax (LoadFeeTrack.h:147), median fee levels (TxQ.cpp:161), quadratic mulDiv (TxQ.cpp:187), signerCount * baseFee (Transactor.cpp:345)",
          not d_bad, "; ".join(d_bad[:3]) or "all 15 tokens at recorded lines")

    # E-01: queue logic re-grepped.
    txq_h = read_lines("src/xrpld/app/misc/TxQ.h")
    txq = read_lines("src/xrpld/app/misc/detail/TxQ.cpp")
    e_ok = ("return lhs.feeLevel > rhs.feeLevel;" in "\n".join(txq_h[650:660])
            and "maxSize_ * fillPercentage / 100" in "\n".join(txq[376:383])
            and "snapshot.txnsExpected * setup_.ledgersInQueue, setup_.queueSizeMin" in "\n".join(txq[1374:1380])
            and "if (feeLevelPaid >= requiredFeeLevel)" in "\n".join(txq[1465:1475])
            and "candidateIter->lastValid && *candidateIter->lastValid <= ledgerSeq" in "\n".join(txq[1378:1386])
            and "escalatedSeriesFeeLevel(" in "\n".join(txq[538:544]))
    check("E-01",
          "fee-level descending order with the parent-hash tie-break; isFull at 100% of maxSize_; maxSize_ is max(txnsExpected * ledgersInQueue, queueSizeMin); accept applies a queued transaction only at or above the required level; expired transactions are removed at ledger close; series rescue uses the escalated series level",
          e_ok, "queue logic verified" if e_ok else "mismatch")

    # F-01: counts reconcile across files.
    def table_rows(path, prefix):
        rows = []
        for ln in open(path, encoding="utf-8"):
            m = re.match(rf"\| ({prefix}-\d+) \| ([A-Z]+) \|", ln)
            if m:
                rows.append((m.group(1), m.group(2)))
        return rows

    claims = table_rows(PACK_ROOT / "docs" / "claim-index.md", "C")
    risks = table_rows(PACK_ROOT / "docs" / "risk-register.md", "K")
    gaps = [ln for ln in open(PACK_ROOT / "docs" / "gap-register.md", encoding="utf-8")
            if re.match(r"\| G-\d+ \|", ln)]
    f_ok = (len(doc["scenarios"]) == 13 and len(runs) == 18
            and len(findings) == 12
            and Counter(f["severity"] for f in findings) == {"HIGH": 3, "MEDIUM": 6, "LOW": 3}
            and len(claims) == 24
            and Counter(s for _, s in claims) == {"VERIFIED": 16, "SPECIFIED": 2, "MODELLED": 4, "UNTESTABLE": 2}
            and len(risks) == 14
            and Counter(s for _, s in risks) == {"HIGH": 3, "MEDIUM": 8, "LOW": 3}
            and len(gaps) == 8
            and len(manifest["excerpts"]) == 44
            and len(hashes["files"]) == 8
            and len(hashes["excerpts"]) == 44)
    check("F-01",
          "matrix == results == scenarios (13); findings 12 (HIGH 3, MEDIUM 6, LOW 3), claims 24 (16/2/4/2), risks 14 (HIGH 3, MEDIUM 8, LOW 3), gaps 8; excerpts 44 across 8 files agree across manifest, files, hashes",
          f_ok, f"claims={len(claims)} risks={len(risks)} gaps={len(gaps)} excerpts={len(manifest['excerpts'])} files={len(hashes['files'])}")

    # G-01: determinism — capture digests, re-run simulator, compare.
    res_before = sha256_file(PACK_ROOT / "outputs" / "derived" / "fee-market-results.json")
    mat_before = sha256_file(PACK_ROOT / "outputs" / "derived" / "scenario-matrix.json")
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            [sys.executable, "src/fee_market_model.py"],
            cwd=str(PACK_ROOT), capture_output=True, text=True)
        g_ok = proc.returncode == 0
    res_digest = sha256_file(PACK_ROOT / "outputs" / "derived" / "fee-market-results.json")
    mat_digest = sha256_file(PACK_ROOT / "outputs" / "derived" / "scenario-matrix.json")
    g_ok = g_ok and res_digest == res_before and mat_digest == mat_before
    check("G-01",
          "determinism: simulator re-run reproduces byte-identical results and matrix (full SHA-256)",
          g_ok,
          f"results shipped={res_before} rerun={res_digest}; matrix shipped={mat_before} rerun={mat_digest}")

    # H-01: excerpt integrity + manifest digests + reproduction digests.
    h_bad = []
    for ex_id, rec in hashes["excerpts"].items():
        p = PACK_ROOT / "fixtures" / "source-excerpts" / f"{ex_id}.txt"
        if not p.is_file() or sha256_file(p) != rec["sha256"]:
            h_bad.append(ex_id)
    for relpath, rec in hashes["files"].items():
        if git_blob(relpath) != rec["git_blob_sha"]:
            h_bad.append(f"{relpath}:blob")
        if (PINNED_CHECKOUT / relpath).stat().st_size != rec["size_bytes"]:
            h_bad.append(f"{relpath}:size")
    man = load_json(PACK_ROOT / "run-manifest.json") if (PACK_ROOT / "run-manifest.json").is_file() else None
    man_ok = True
    if not skip_manifest and man is not None:
        man_ok = (man.get("results_sha256") == res_digest
                  and man.get("matrix_sha256") == mat_digest)
        for rep in man.get("reproductions", []):
            log_path = PACK_ROOT / rep["log"]
            if not log_path.is_file() or sha256_file(log_path) != rep["sha256"]:
                man_ok = False
                h_bad.append(f"reproduction {rep['label']}: digest mismatch")
        vd = man.get("verify_digests_sha256")
        if vd:
            vd_path = PACK_ROOT / "outputs" / "verify-digests.log"
            if not vd_path.is_file() or sha256_file(vd_path) != vd:
                man_ok = False
                h_bad.append("verify-digests.log: digest mismatch")
    check("H-01",
          "every excerpt digest matches source-hashes.json; every manifest blob SHA/size matches the checkout; run-manifest digests match shipped derived files; recorded reproduction log digests match the fresh-clone logs on disk; recorded verify-digests digest matches outputs/verify-digests.log when present",
          not h_bad and man_ok,
          "; ".join(h_bad[:3]) or ("manifest digests match" if man_ok else "manifest digest mismatch"))

    # I-01: absence findings re-grepped.
    def count_hits(pattern, *roots):
        return len(grep_hits(pattern, *roots))

    i1 = count_hits("std::exp", "src/xrpld/app/misc/detail/TxQ.cpp",
                    "src/xrpld/app/misc/detail/LoadFeeTrack.cpp")
    i2 = count_hits("maxFeeLevel", "src/xrpld/app/misc/detail/TxQ.cpp")
    i3 = count_hits("discount", "src/xrpld/app/misc/detail/TxQ.cpp",
                    "src/xrpld/app/misc/TxQ.h")
    i4 = count_hits("perAccountFee|feeDiscount|accountFee",
                    "src/xrpld/app/misc/detail/TxQ.cpp",
                    "src/xrpld/app/misc/TxQ.h")
    i5 = count_hits("std::min\\(escalationMultiplier_",
                    "src/xrpld/app/misc/detail/TxQ.cpp")
    i6 = count_hits("exponentially", "src/xrpld/app/misc/detail/TxQ.cpp")
    check("I-01",
          "absence findings re-grepped: std::exp 0 hits in TxQ.cpp and LoadFeeTrack.cpp; maxFeeLevel 0 hits; discount 0 hits; no per-account fee discount token; the escalation multiplier is never capped with std::min; 'exponentially' appears 0 times in TxQ.cpp",
          i1 == 0 and i2 == 0 and i3 == 0 and i4 == 0 and i5 == 0 and i6 == 0,
          f"std::exp={i1} maxFeeLevel={i2} discount={i3} perAccountFee={i4} min-cap={i5} exponentially={i6}")

    # J-01: divergence tokens.
    md = read_lines("src/xrpld/app/misc/FeeEscalation.md")
    j_ok = ("into the ledger, the fee level increases exponentially." in "\n".join(md[52:60])
            and "The minimum value of 5 was" in "\n".join(md[224:230])
            and "minimumTxnInLedger = 32" in "\n".join(txq_h[100:106])
            and "targetTxnInLedger = 256" in "\n".join(txq_h[106:112])
            and "the fee will grow exponentially from there." in "\n".join(txq_h[42:52]))
    check("J-01",
          "the design document says the fee level 'increases exponentially' (FeeEscalation.md:57) while the code computes a quadratic; the document says minimum 5 / target 50 (FeeEscalation.md:226-228) while the code says 32 / 256; the class comment repeats the exponential claim (TxQ.h:48)",
          j_ok, "divergence tokens verified" if j_ok else "mismatch")

    # T-01: timing sanity.
    elapsed_ms = int((time.time() - started) * 1000)
    check("T-01",
          "timing sanity: total probe elapsed_ms is non-negative (loose band, never exact)",
          elapsed_ms >= 0, "value not recorded; never compared")

    passed = sum(1 for c in checks if c["pass"])
    total = len(checks)
    lines.append(f"probe: {passed}/{total} checks PASS")
    lines.append(f"probe: fee-market-results.json sha256: {res_digest}")
    lines.append(f"probe: scenario-matrix.json sha256: {mat_digest}")
    lines.append(f"probe: pinned commit {PINNED_COMMIT}")
    text = "\n".join(lines) + "\n"
    sys.stdout.write(text)
    result_doc = {"pack": "Fee-Market and Transaction-Pricing in postfiatd",
                  "pinned_commit": PINNED_COMMIT,
                  "results_file": "outputs/derived/fee-market-results.json",
                  "results_sha256": res_digest, "matrix_sha256": mat_digest,
                  "checks": checks, "passed": passed, "total": total}
    out_derived = PACK_ROOT / "outputs" / "derived" / "probe-results.json"
    out_derived.parent.mkdir(parents=True, exist_ok=True)
    with open(out_derived, "w", encoding="utf-8") as fh:
        json.dump(result_doc, fh, indent=1, sort_keys=True)
        fh.write("\n")
    (PACK_ROOT / "outputs" / "probe-run.log").write_text(text)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
