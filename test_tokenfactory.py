"""Phase 1 probe: can Token Factory's Nemotron models chat and call tools?

Usage (PowerShell):
    $env:TOKENFACTORY_API_KEY = "your-key"
    py test_tokenfactory.py

Optional env vars: KEEPER_MODELS (comma-separated ids), TOKENFACTORY_BASE_URL,
KEEPER_TIMEOUT_S, KEEPER_MAX_TOKENS.
"""
import sys

from keeper_probe import catalog, probes, report
from keeper_probe.client import make_client
from keeper_probe.config import load_settings


def main() -> int:
    settings = load_settings()
    client = make_client(settings)

    try:
        available = catalog.list_model_ids(client)
    except Exception as exc:
        print(f"Could not list models ({type(exc).__name__}: {exc}). Probing ids as given.")
        available = []
    if available:
        report.print_catalog(catalog.nemotron_ids(available))

    rows = []
    skipped = []
    for requested in settings.models:
        model = requested
        if available:
            res = catalog.resolve(requested, available)
            if res.resolved is None:
                print(f"{requested}: {res.note}. Skipping.\n")
                skipped.append(requested)
                continue
            model = res.resolved
            if res.note != "ok":
                print(f"{requested}: {res.note}")
        print(model)
        plain = probes.plain_chat(client, model, settings.max_tokens)
        report.print_row(model, plain)
        tool = probes.tool_call(client, model, settings.max_tokens)
        report.print_row(model, tool)
        print()
        rows.append((model, plain, tool))

    report.print_summary(rows, skipped)
    all_ok = bool(rows) and not skipped and all(p.ok and t.ok for _, p, t in rows)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
