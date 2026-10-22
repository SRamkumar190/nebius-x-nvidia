"""Run one Hermes one-shot chat and report how its system prompt gets built.

    python3 -I hermes_trace.py "<question>"

`keeper skills trace-prompt` runs this with Hermes's own Python in isolated
mode (-I). It imports nothing from Keeper. It starts Hermes's real CLI entry
point (`hermes chat --oneshot -q <question>`) with a profiler hook and prints
`[trace]` lines to stderr:

- every write to HERMES_IGNORE_RULES, with the code that made it
- the skip_context_files / skip_memory flags each AIAgent is built with
- each call to a function with "soul" in its name, and what it returned
- the first line of every system prompt Hermes builds
- each Hermes home directory Hermes resolves
"""
import os
import sys
import threading
import traceback

WATCH_ENV = ("HERMES_IGNORE_RULES", "HERMES_SAFE_MODE", "HERMES_HOME")
_seen_homes = set()


_said = set()


def _say(text):
    if text in _said:  # a helper Hermes calls often would flood the screen
        return
    _said.add(text)
    sys.stderr.write("[trace] " + text + "\n")
    sys.stderr.flush()


def _short(value, limit=120):
    if value is None:
        return "None"
    if isinstance(value, str):
        return f"{len(value)} chars: " + " ".join(value.split())[:limit]
    return repr(value)[:limit]


def _where(frame):
    return f"{os.path.basename(frame.f_code.co_filename)}:{frame.f_lineno}"


_original_setitem = os._Environ.__setitem__


def _setitem(self, key, value):
    if key in WATCH_ENV:
        stack = traceback.extract_stack(limit=8)[:-1]
        chain = " <- ".join(f"{os.path.basename(f.filename)}:{f.lineno} {f.name}" for f in reversed(stack))
        _say(f"os.environ[{key!r}] = {value!r} at {chain}")
    return _original_setitem(self, key, value)


def _profile(frame, event, arg):
    if event not in ("call", "return"):
        return
    name = frame.f_code.co_name
    if event == "call":
        if name == "__init__" and type(frame.f_locals.get("self")).__name__ == "AIAgent":
            loc = frame.f_locals
            _say(f"AIAgent(skip_context_files={loc.get('skip_context_files')!r}, "
                 f"skip_memory={loc.get('skip_memory')!r}, platform={loc.get('platform')!r}) "
                 f"HERMES_IGNORE_RULES={os.environ.get('HERMES_IGNORE_RULES')!r} "
                 f"HERMES_HOME={os.environ.get('HERMES_HOME')!r}")
        elif "soul" in name.lower():
            args = {k: v for k, v in frame.f_locals.items() if k != "self"}
            _say(f"call {name}({_short(args, 160)}) at {_where(frame)}")
        return
    if "soul" in name.lower():
        _say(f"{name} returned {_short(arg)}")
    elif name in ("_build_system_prompt", "build_system_prompt") and isinstance(arg, str):
        _say(f"{name} built a prompt starting: {_short(arg, 100)}")
    elif name in ("get_hermes_home", "_get_hermes_home") and arg is not None and str(arg) not in _seen_homes:
        _seen_homes.add(str(arg))
        _say(f"Hermes home resolved to {arg}")


def main(argv):
    question = argv[0] if argv else "In one line, what is your name?"
    os.environ.setdefault("HERMES_SKIP_CHMOD", "1")  # NemoClaw's hermes wrapper sets this too
    os._Environ.__setitem__ = _setitem
    threading.setprofile(_profile)
    sys.setprofile(_profile)
    sys.argv = ["hermes", "chat", "--oneshot", "-q", question]
    try:  # Hermes's editable install already puts its source on the path, after site-packages
        from hermes_cli.main import main as hermes_main
    except ImportError:
        sys.path.append(os.environ.get("KEEPER_HERMES_SRC", "/opt/hermes"))
        from hermes_cli.main import main as hermes_main
    return hermes_main()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
