"""CLI:  python cli.py demo | experiments | generate | case <case_id>"""
import argparse
import json
import os
from aiops_agent.generator import generate_dataset, save_jsonl, load_jsonl
from aiops_agent.workflow import run_incident, HAVE_LANGGRAPH
from aiops_agent.evaluation import run_all, build_report
from aiops_agent import reporting


def demo(args):
    cases = generate_dataset(args.seed)
    c = next(x for x in cases if x["scenario_type"] == args.scenario)
    s = run_incident(c)
    print(f"[engine={s['engine']}, langgraph_installed={HAVE_LANGGRAPH}]  SYNTHETIC case {c['case_id']} ({c['scenario_type']})")
    for t in s["trace"]:
        print(f"  {t['node']:<10} {t['msg']}")
    print("\nFinal status:", s["status"], "|", s.get("escalation_reason", ""))
    print("Ground truth: cause =", c["root_cause"], "| expected_final =", c["expected_final"])
    if args.json:
        print(json.dumps(build_report(c, s), indent=1, default=str))


def experiments(args):
    run_all(args.out, seeds=tuple(args.seeds))
    reporting.make_latex(args.out)
    ok = reporting.make_plots(args.out)
    print(f"Wrote results to {args.out}/ (plots={'yes' if ok else 'skipped: matplotlib missing'})")


def generate(args):
    save_jsonl(generate_dataset(args.seed), args.path)
    print("wrote", args.path)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd", required=True)
    d = sp.add_parser("demo"); d.add_argument("--scenario", default="db_pool_exhaustion"); d.add_argument("--seed", type=int, default=42)
    d.add_argument("--json", action="store_true"); d.set_defaults(f=demo)
    e = sp.add_parser("experiments"); e.add_argument("--out", default="results"); e.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46]); e.set_defaults(f=experiments)
    g = sp.add_parser("generate"); g.add_argument("--seed", type=int, default=42); g.add_argument("--path", default="data/sample_dataset.jsonl"); g.set_defaults(f=generate)
    a = p.parse_args(); a.f(a)
