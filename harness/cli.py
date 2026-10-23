"""Command line for the harness runtime.

Usage:
    python3 -m harness init
    python3 -m harness add --id H02 --name "..." --claim "..." --level Meso \
        --tier standard -- python3 -m pytest -q tests/test_x.py
    python3 -m harness run H02
    python3 -m harness run-governed H02 --receipt-public-key FILE
    python3 -m harness resume
    python3 -m harness review H02 --verdict evidenced --reviewer skeptic-01 \
        --challenge "attack whether ..."
    python3 -m harness verify --require-complete
    python3 -m harness audit --out docs/HARNESS_AUDIT_G00.json
"""

import argparse
import json
import sys

from harness import RUNTIME_VERSION, governance, kernel
from harness.audit import run_audit, write_report
from harness.contracts import ContractError, GateSpec, TaskContract
from harness.store import InvalidTransition, StoreError
from harness.runtime import Executor

RUN_FAILURE_STATES = {"FAILED", "BLOCKED", "INTERRUPTED"}


def _result_exit_code(results):
    states = [item.get("state") for item in results]
    if not states:
        return 3
    if any(state in RUN_FAILURE_STATES for state in states):
        return 1
    if any(state != "SUCCEEDED" for state in states):
        return 3
    return 0


def _print_results(results):
    for result in results:
        if result.get("error"):
            print(
                f"  [{result['state']}] {result['task_id']} attempt "
                f"{result.get('attempt_no')} error={result['error']}"
            )
        else:
            print(
                f"  [{result['state']}] {result['task_id']} attempt "
                f"{result.get('attempt_no')} capture={result.get('capture_status')} "
                f"exit={result.get('return_code')}"
            )
        if result.get("review_required"):
            print(f"      next: python3 -m harness review {result['task_id']} ...")


def cmd_init(args):
    executor = Executor(args.root, builder=args.builder)
    store = executor.initialize()
    print(f"[INIT] {store.db_path}")
    print(f"[LEDGER] {store.ledger_path}")
    print(f"[ATTESTATIONS] {store.attest_dir}")
    return 0


def _contract_from_args(args, gate):
    if args.contract:
        with open(args.contract, encoding="utf-8") as handle:
            document = json.load(handle)
        return TaskContract.from_dict(document)
    missing = [
        label
        for label, value in (
            ("--id", args.task_id),
            ("--name", args.name),
            ("--claim", args.claim),
        )
        if not value
    ]
    if missing:
        raise ContractError("missing required option(s): " + ", ".join(missing))
    if gate is None or not gate:
        raise ContractError("supply the real gate after `--`")
    review = args.require_review
    return TaskContract(
        task_id=args.task_id,
        name=args.name,
        claim=args.claim,
        level=args.level,
        tier=args.tier,
        gate=GateSpec(
            command=tuple(gate),
            timeout_seconds=args.timeout,
            files=tuple(args.file),
            optional_files=tuple(args.optional_file),
        ),
        max_attempts=args.max_attempts,
        require_review=review,
    )


def cmd_add(args, gate):
    executor = Executor(args.root, builder=args.builder)
    executor.store.ensure_initialized()
    contract = _contract_from_args(args, gate)
    task = executor.register(contract)
    print(f"[REGISTERED] {task.task_id} state={task.state} tier={contract.tier}")
    print(f"[CONTRACT] sha256={contract.digest()}")
    print(f"[GATE] {contract.gate.command_string()}")
    if contract.require_review:
        print("[REVIEW] independent review will be required before SUCCEEDED")
    return 0


def cmd_run(args):
    executor = Executor(
        args.root, builder=args.builder, lease_seconds=args.lease_seconds
    )
    executor.store.ensure_initialized()
    targets = list(args.task_ids)
    if not targets:
        if not args.all:
            print("ERROR: name task ids or pass --all", file=sys.stderr)
            return 2
        targets = [task.task_id for task in executor.store.list_tasks(state="READY")]
    results = []
    for task_id in targets:
        results.append(executor.run(task_id))
    _print_results(results)
    if not results:
        print("[RUN] no READY task")
        return 0
    return _result_exit_code(results)


def cmd_run_governed(args):
    from harness import governed

    executor = Executor(
        args.root, builder=args.builder, lease_seconds=args.lease_seconds
    )
    executor.store.ensure_initialized()
    config = governed.GovernanceConfig.for_root(
        args.root,
        pin=args.pin,
        home=args.home,
        node=args.node,
        receipt_public_key=args.receipt_public_key,
        timeout=args.timeout,
    )
    task_ids = list(args.task_ids)
    if not task_ids:
        if not args.all:
            print("ERROR: name task ids or pass --all", file=sys.stderr)
            return 2
        task_ids = [
            task.task_id for task in executor.store.list_tasks(state="READY")
        ]
    results = []
    for task_id in task_ids:
        try:
            results.append(
                governed.run(
                    executor,
                    task_id,
                    config,
                    advisory=args.advisory,
                    retry_reason=args.retry_reason,
                )
            )
        except governed.GovernanceDenied as error:
            print(f"  [BLOCKED] {task_id} {error}")
            return 1
        except governed.governance.GovernanceUnavailable as error:
            print(f"  [BLOCKED] {task_id} governance: {error}")
            return 1
    _print_results(results)
    for result in results:
        summary = result.get("governance")
        if not summary:
            continue
        print(
            f"      [GOVERNED] receipt={summary['receipt_id']} "
            f"binding={summary['binding_digest'][:12]} "
            f"signature={summary['checks'].get('signature')}"
        )
    if not results:
        print("[GOVERNED] no task to run")
        return 0
    return _result_exit_code(results)


def cmd_resume(args):
    executor = Executor(
        args.root, builder=args.builder, lease_seconds=args.lease_seconds
    )
    executor.store.ensure_initialized()
    outcome = executor.resume(args.task_ids or None, retry=not args.no_retry)
    for item in outcome["reaped"]:
        print(
            f"[REAPED] {item['task_id']} attempt {item['attempt_no']}: {item['reason']}"
        )
    _print_results(outcome["results"])
    if not outcome["reaped"] and not outcome["results"]:
        print("[RESUME] nothing to recover or run")
        return 0
    return _result_exit_code(outcome["results"])


def cmd_review(args):
    executor = Executor(args.root, builder=args.builder)
    executor.store.ensure_initialized()
    result = executor.review(
        args.task_id,
        args.verdict,
        args.reviewer,
        args.challenge,
        automatic=args.automatic,
    )
    print(f"[{result['state']}] {args.task_id} verdict={result['verdict']}")
    print(f"[REVIEW] {result['review_path']} sha256={result['review_digest']}")
    return 0 if result["state"] == "SUCCEEDED" else 1


def cmd_retry(args):
    executor = Executor(args.root, builder=args.builder)
    executor.store.ensure_initialized()
    executor.retry(args.task_id, args.reason)
    return 0


def cmd_status(args):
    executor = Executor(args.root, builder=args.builder)
    executor.store.ensure_initialized()
    rows = executor.status()
    if not rows:
        print("[STATUS] no task registered")
        return 0
    print(f"  {'TASK':<24} {'STATE':<16} {'TIER':<10} {'ATTEMPTS':<9} REVIEW")
    for row in rows:
        attempts = f"{row['attempts']}/{row['max_attempts']}"
        print(
            f"  {row['task_id']:<24} {row['state']:<16} {row['tier']:<10} "
            f"{attempts:<9} {row['review_verdict'] or '-'}"
        )
    return 0


def cmd_verify(args):
    from harness import governed

    executor = Executor(args.root, builder=args.builder)
    executor.store.ensure_initialized()
    config = governed.GovernanceConfig.for_root(
        args.root,
        pin=args.pin,
        home=args.home,
        node=args.node,
        receipt_public_key=args.receipt_public_key,
    )
    problems, summary = executor.verify(
        require_complete=args.require_complete, governance_config=config
    )
    print(
        f"[VERIFY] tasks={summary['tasks']} succeeded={summary['succeeded']} "
        f"proofs={summary['proofs']}"
    )
    if summary["pending"]:
        print("[PENDING] " + ", ".join(summary["pending"]))
    for problem in problems:
        print(f"  - {problem}")
    if problems:
        print(f"VERIFY FAILED — {len(problems)} problem(s)")
        return 1
    print("VERIFY OK")
    return 0


def cmd_governance(args):
    status = governance.check(pin_path=args.pin, home=args.home)
    print(f"[GOVERNANCE] {status.status}")
    if status.pin_digest:
        print(f"  pin sha256={status.pin_digest}")
    if status.veor_home:
        print(f"  home={status.veor_home}")
    if status.node:
        print(f"  node={status.node}")
    for reason in status.reasons:
        print(f"  - {reason}")
    if not status.ready:
        print("  governance is optional and blocked; the proof path is unaffected")
    return 0 if status.ready else 3


def cmd_audit(args):
    report = run_audit(args.root, include_gates=not args.no_gates)
    write_report(report, args.out, args.markdown)
    if not args.quiet:
        print(f"[AUDIT] {args.out}")
        if args.markdown:
            print(f"[AUDIT] {args.markdown}")
        for gate in report["reference_gates"]:
            print(
                f"  [{'PASS' if gate['exit_code'] == 0 else 'FAIL'}] "
                f"{gate['name']} exit={gate['exit_code']} {gate['duration_ms']}ms"
            )
    failing = [gate for gate in report["reference_gates"] if gate["exit_code"] != 0]
    if failing:
        print(f"AUDIT FAILED — {len(failing)} reference gate(s) failed")
        return 1
    return 0


def cmd_selftest(args):
    import tempfile

    results = []

    def check(name, value):
        results.append((name, bool(value)))

    with tempfile.TemporaryDirectory(prefix="harness-selftest-") as directory:
        executor = Executor(directory, builder="selftest-builder", quiet=True)
        executor.initialize()
        contract = TaskContract(
            task_id="S1",
            name="selftest lite gate",
            claim="the selftest gate executes through the proof kernel",
            level="Micro",
            tier="lite",
            gate=GateSpec(command=(sys.executable, "-c", "print('selftest ok')")),
        )
        task = executor.register(contract)
        check("registered_pending", task.state == "PENDING")
        result = executor.run("S1")
        check("lite_reaches_succeeded", result["state"] == "SUCCEEDED")
        check(
            "proof_persisted",
            executor.store.latest_proof("S1") is not None,
        )
        problems, _summary = executor.verify(require_complete=True)
        check("verify_clean", not problems)
        try:
            executor.store.transition("S1", "READY")
        except InvalidTransition:
            check("terminal_state_guarded", True)
        else:
            check("terminal_state_guarded", False)
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    passed = sum(value for _name, value in results)
    print(f"self-test: {passed}/{len(results)} passed ({RUNTIME_VERSION})")
    return 0 if passed == len(results) else 2


def build_parser():
    parser = argparse.ArgumentParser(prog="harness")
    parser.add_argument("--version", action="version", version=f"harness {RUNTIME_VERSION}")
    parser.add_argument("--root", default=".", help="project root owning .harness/")
    parser.add_argument("--builder", default=None)
    subparsers = parser.add_subparsers(dest="command_name")

    init = subparsers.add_parser("init", help="create the runtime store")
    init.set_defaults(func=cmd_init)

    add = subparsers.add_parser("add", help="register a typed task contract")
    add.add_argument("--contract", help="JSON contract file")
    add.add_argument("--id", dest="task_id")
    add.add_argument("--name")
    add.add_argument("--claim")
    add.add_argument("--level", default="Micro", choices=("Macro", "Meso", "Micro", "Nano"))
    add.add_argument("--tier", default="standard", choices=("lite", "standard", "regulated"))
    add.add_argument("--timeout", type=float)
    add.add_argument("--file", action="append", default=[])
    add.add_argument("--optional-file", action="append", default=[])
    add.add_argument("--max-attempts", type=int, default=3)
    review_group = add.add_mutually_exclusive_group()
    review_group.add_argument("--require-review", dest="require_review", action="store_true")
    review_group.add_argument("--no-review", dest="require_review", action="store_false")
    add.set_defaults(require_review=None)
    add.set_defaults(func=None)  # gate is supplied after `--`

    run = subparsers.add_parser("run", help="execute READY tasks")
    run.add_argument("task_ids", nargs="*")
    run.add_argument("--all", action="store_true")
    run.add_argument("--lease-seconds", type=float, default=900)
    run.set_defaults(func=cmd_run)

    run_governed = subparsers.add_parser(
        "run-governed",
        help="execute READY tasks only after a VEOR decision and a verified receipt",
    )
    run_governed.add_argument("task_ids", nargs="*")
    run_governed.add_argument("--all", action="store_true")
    run_governed.add_argument("--lease-seconds", type=float, default=900)
    run_governed.add_argument("--pin", default=None)
    run_governed.add_argument("--home", default=None)
    run_governed.add_argument("--node", default=None)
    run_governed.add_argument(
        "--receipt-public-key", dest="receipt_public_key", default=None
    )
    run_governed.add_argument("--timeout", type=float, default=60.0)
    run_governed.add_argument(
        "--advisory", default="ALLOW", choices=("ALLOW", "REVIEW", "DENY")
    )
    run_governed.add_argument("--retry-reason", dest="retry_reason", default=None)
    run_governed.set_defaults(func=cmd_run_governed)

    resume = subparsers.add_parser("resume", help="recover interrupted work and continue")
    resume.add_argument("task_ids", nargs="*")
    resume.add_argument("--no-retry", action="store_true")
    resume.add_argument("--lease-seconds", type=float, default=900)
    resume.set_defaults(func=cmd_resume)

    review = subparsers.add_parser("review", help="review a pending capture")
    review.add_argument("task_id")
    review.add_argument(
        "--verdict", required=True, choices=("evidenced", "insufficient", "disproven")
    )
    review.add_argument("--reviewer", required=True)
    review.add_argument("--challenge", required=True)
    review.add_argument("--automatic", action="store_true")
    review.set_defaults(func=cmd_review)

    retry = subparsers.add_parser("retry", help="schedule a retry with a stated reason")
    retry.add_argument("task_id")
    retry.add_argument("--reason", required=True)
    retry.set_defaults(func=cmd_retry)

    status = subparsers.add_parser("status", help="show task states")
    status.set_defaults(func=cmd_status)

    verify = subparsers.add_parser("verify", help="re-verify proofs, journal and ledger")
    verify.add_argument("--require-complete", action="store_true")
    verify.add_argument("--pin", default=None, help="VEOR pin (governed tasks)")
    verify.add_argument("--home", default=None, help="pinned VEOR checkout")
    verify.add_argument("--node", default=None)
    verify.add_argument("--receipt-public-key", dest="receipt_public_key", default=None)
    verify.set_defaults(func=cmd_verify)

    gov = subparsers.add_parser(
        "governance", help="report the optional pinned VEOR sidecar (G02)"
    )
    gov.add_argument("--pin", default="tools/veor-pin.json")
    gov.add_argument("--home")
    gov.set_defaults(func=cmd_governance)

    audit = subparsers.add_parser("audit", help="G00 audit: inventory + reference gates")
    audit.add_argument("--out", default=".harness-artifacts/g00-audit.json")
    audit.add_argument("--markdown", default=None)
    audit.add_argument("--no-gates", action="store_true")
    audit.add_argument("--quiet", action="store_true")
    audit.set_defaults(func=cmd_audit)

    selftest = subparsers.add_parser("selftest", help="embedded end-to-end smoke gate")
    selftest.set_defaults(func=cmd_selftest)
    return parser


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    gate = None
    if "--" in argv:
        separator = argv.index("--")
        argv, gate = argv[:separator], argv[separator + 1 :]
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        if args.command_name == "add":
            try:
                return cmd_add(args, gate)
            except (ContractError, StoreError, OSError, ValueError) as error:
                print(f"ERROR: {error}", file=sys.stderr)
                return 2
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except (ContractError, StoreError, InvalidTransition, OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    except kernel.KernelUnavailable as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
