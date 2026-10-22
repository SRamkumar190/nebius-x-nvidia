"""Ask the installed Hermes what it makes of a SOUL.md file.

    python3 -I hermes_probe.py <SOUL.md> [hermes source dir]

`keeper skills prompt-check` runs this with Hermes's own Python in isolated
mode (-I), so Keeper's packages can't shadow Hermes's. It doesn't import
anything from Keeper. It finds Hermes's context-file scanner by the warning
text the docs quote ("Content not loaded"), runs it on the file, calls
Hermes's SOUL.md loader, and prints one JSON object.
"""
import contextlib
import importlib
import inspect
import json
import os
import pathlib
import sys

SKIP_DIRS = {"node_modules", "tests", "web", "ui-tui", "website", "docs", "skills",
             "optional-skills", "apps", "scripts", "__pycache__"}
BLOCK_TEXT = "Content not loaded"


def _modules_with(root, needle):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(filenames):
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            try:
                with open(path, encoding="utf-8") as fh:
                    if needle not in fh.read():
                        continue
            except (OSError, UnicodeDecodeError):
                continue
            module = os.path.relpath(path, root)[:-3].replace(os.sep, ".")
            yield module[:-len(".__init__")] if module.endswith(".__init__") else module


def _own_functions(module):
    for name, fn in inspect.getmembers(module, inspect.isfunction):
        if fn.__module__ == module.__name__:
            yield name, fn


def _required_args(fn):
    try:
        params = inspect.signature(fn).parameters.values()
    except (TypeError, ValueError):
        return None
    return sum(1 for p in params if p.default is p.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD))


def _short(text, limit=300):
    return " ".join(str(text).split())[:limit]


def _find_scanner(module):
    """The function that writes the warning, or failing that one named like a context scanner."""
    named = None
    for name, fn in _own_functions(module):
        try:
            if BLOCK_TEXT in inspect.getsource(fn):
                return name, fn
        except (OSError, TypeError):
            pass
        if named is None and "scan" in name.lower() and "context" in name.lower():
            named = (name, fn)
    return named


def _scan(fn, text):
    args = (text, "SOUL.md") if _required_args(fn) == 2 else (text,)
    try:
        result = fn(*args)
    except Exception as exc:
        return f"error calling it: {exc.__class__.__name__}: {_short(exc, 160)}"
    if isinstance(result, str) and "BLOCKED" in result[:200]:
        return "BLOCKED: " + _short(result)
    if isinstance(result, str) and result.strip() == text.strip():
        return "passes"
    return f"passes, but returns something else: {_short(result, 160)}"


def probe(soul_path, root):
    out = {}
    with open(soul_path, encoding="utf-8") as fh:
        text = fh.read()
    sys.path.insert(0, root)
    for module_name in _modules_with(root, BLOCK_TEXT):
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # report and keep looking
            out.setdefault("import_errors", []).append(f"{module_name}: {exc.__class__.__name__}: {_short(exc, 160)}")
            continue
        found = _find_scanner(module)
        if not found:
            continue
        name, fn = found
        out["scanner"] = f"{module_name}.{name}"
        out["scan"] = _scan(fn, text)
        identity = getattr(module, "DEFAULT_AGENT_IDENTITY", None)
        if isinstance(identity, str):
            out["fallback_identity"] = _short(identity, 120)
        loader = getattr(module, "load_soul_md", None)
        if callable(loader) and _required_args(loader) == 0:
            # Chats call load_soul_md(home_override=<folder>); ask about the
            # folder this file is in, the way they do.
            kwargs = {}
            try:
                if "home_override" in inspect.signature(loader).parameters:
                    kwargs["home_override"] = pathlib.Path(soul_path).parent
            except (TypeError, ValueError):
                pass
            try:
                loaded = loader(**kwargs)
                out["load_soul_md"] = None if loaded is None else f"{len(loaded)} chars: {_short(loaded, 120)}"
            except Exception as exc:
                out["load_soul_md"] = f"error: {exc.__class__.__name__}: {_short(exc, 160)}"
            if kwargs:
                out["load_soul_md_home"] = str(kwargs["home_override"])
        return out
    out["scan"] = f"couldn't find Hermes's scanner under {root}"
    return out


def main(argv):
    if not argv:
        print("usage: hermes_probe.py <SOUL.md> [hermes source dir]", file=sys.stderr)
        return 2
    root = argv[1] if len(argv) > 1 else "/opt/hermes"
    # Hermes may log to stdout while it imports; keep the JSON line clean.
    with contextlib.redirect_stdout(sys.stderr):
        try:
            out = probe(argv[0], root)
        except Exception as exc:
            out = {"scan": f"probe failed: {exc.__class__.__name__}: {_short(exc, 200)}"}
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
