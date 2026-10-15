"""Plain-ASCII output so it prints cleanly in a Windows PowerShell 5.1 console."""
from .probes import ProbeResult


def _tokens(r: ProbeResult) -> str:
    if r.prompt_tokens is None:
        return "-"
    return f"{r.prompt_tokens}+{r.completion_tokens}"


def print_catalog(nemotron: list[str]) -> None:
    print("Nemotron models in the Token Factory catalog:")
    for mid in nemotron or ["(none found)"]:
        print(f"  {mid}")
    print()


def print_row(model: str, r: ProbeResult) -> None:
    status = "OK  " if r.ok else "FAIL"
    if r.error:
        line = f"ERROR {r.error[:160]}"
    else:
        line = f"{r.latency_s:6.2f}s  tokens(in+out)={_tokens(r):<10} finish={r.finish_reason}  {r.detail}"
    print(f"  [{status}] {r.kind:<5} {line}")


def print_summary(rows: list[tuple[str, ProbeResult, ProbeResult]], skipped: list[str]) -> None:
    print()
    print("Summary")
    print(f"  {'model':<40} {'plain':<6} {'tools':<6} {'plain s':>8} {'tool s':>8}")
    for model, plain, tool in rows:
        print(
            f"  {model:<40} {'yes' if plain.ok else 'NO':<6} {'yes' if tool.ok else 'NO':<6}"
            f" {plain.latency_s:8.2f} {tool.latency_s:8.2f}"
        )
    for model in skipped:
        print(f"  {model:<40} skipped (not in catalog)")
