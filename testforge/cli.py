import argparse
import json
import sys

from .runner import run_mutation


def main(argv=None):
    ap = argparse.ArgumentParser(prog="testforge")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mutate", help="score a test suite by injecting bugs into the code")
    m.add_argument("--project", required=True, help="project root (contains the tests)")
    m.add_argument("--target", required=True, help="file to mutate, relative to project")
    m.add_argument("--test-cmd", default="pytest -x -q", help="how to run the tests")
    m.add_argument("--max", type=int, default=0, help="sample at most N mutants (0 = all)")
    m.add_argument("--seed", type=int, default=0)
    m.add_argument("--timeout", type=int, default=60)
    m.add_argument("--json", help="write raw results here")
    m.add_argument("--html", help="write an HTML report here")
    g = sub.add_parser("auto", help="generate tests with an LLM, score them, improve them, report")
    g.add_argument("--project", required=True)
    g.add_argument("--target", required=True)
    g.add_argument("--spec", required=True, help="OpenAPI JSON file")
    g.add_argument("--provider", default="groq", choices=["groq", "anthropic"])
    g.add_argument("--max", type=int, default=0)
    g.add_argument("--seed", type=int, default=0)
    g.add_argument("--html", default="testforge_report.html")
    g.add_argument("--model", help="model id")
    a = ap.parse_args(argv)

    if a.cmd == "auto":
        from .pipeline import auto
        from .providers import get_provider
        spec = json.load(open(a.spec))
        out = auto(get_provider(a.provider, a.model), a.project, a.target, spec, a.max, a.seed, a.html)
        print(json.dumps(out, indent=2))
        return

    if a.cmd == "mutate":
        res = run_mutation(a.project, a.target, a.test_cmd, a.timeout, a.max, a.seed)
        print(f"\nMutation score: {res['score']}%  ({res['killed']}/{res['total']} killed)")
        for r in res["results"]:
            if r["status"] == "survived":
                print(f"  SURVIVED line {r['line']}: {r['original']}  ->  {r['mutated']}")
        if a.json:
            json.dump(res, open(a.json, "w"), indent=2)
        if a.html:
            from .report import write
            write({"this run": res}, a.html)


if __name__ == "__main__":
    sys.exit(main())
