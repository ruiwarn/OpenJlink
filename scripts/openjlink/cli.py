import argparse
import inspect
import json
import sys
import types
import typing
from openjlink import __version__
from openjlink.api import EXTRAS, OFFLINE, call, catalog, signature
from openjlink.session import Workbench


def emit(value):
    print(json.dumps(value, ensure_ascii=False, allow_nan=False), flush=True)


def argument_type(annotation):
    if typing.get_origin(annotation) in (typing.Union, types.UnionType):
        choices = [a for a in typing.get_args(annotation) if a is not type(None)]
        return argument_type(choices[0]) if len(choices) == 1 else json.loads
    if annotation is int:
        return lambda value: int(value, 0)
    return annotation if annotation in (str, float) else json.loads


def main():
    sys.stdin.reconfigure(encoding="utf-8-sig")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    state_help = "Writable task state directory for sessions/jobs"
    parser = argparse.ArgumentParser(prog="openjlink")
    parser.add_argument("--version", action="version", version="OpenJlink " + __version__)
    parser.add_argument("--state-dir", help=state_help)
    sub = parser.add_subparsers(dest="mode", required=True)
    schema = sub.add_parser("schema")
    schema.add_argument("operation", nargs="?", choices=list(catalog()))
    single = sub.add_parser("call")
    single.add_argument("--state-dir", default=argparse.SUPPRESS, help=state_help)
    single.add_argument("operation", choices=list(catalog()))
    single.add_argument("--args", default="{}", help="JSON object or @UTF-8-file.json")
    session_parser = sub.add_parser(
        "session",
        help="Persistent newline JSON requests and immediate responses",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Persistent newline-delimited JSON-RPC over stdin/stdout (keeps connect/load_symbols state).",
        epilog='Request:  {"id": 1, "operation": "connect", "arguments": {"serial": 123, "device": "Cortex-M0"}}\nResponse: {"id": 1, "ok": true, "result": {...}}',
    )
    session_parser.add_argument("--state-dir", default=argparse.SUPPRESS, help=state_help)
    for name, info in catalog().items():
        direct = sub.add_parser(name.replace("_", "-"), help=info["description"])
        direct.set_defaults(operation=name)
        direct.add_argument("--state-dir", default=argparse.SUPPRESS, help=state_help)
        for parameter in signature(name).parameters.values():
            options = {"dest": parameter.name}
            if parameter.annotation is bool:
                options["action"] = argparse.BooleanOptionalAction
            else:
                options["type"] = argument_type(parameter.annotation)
            if parameter.default is inspect.Parameter.empty:
                options["required"] = True
            else:
                options["default"] = parameter.default
            direct.add_argument("--" + parameter.name.replace("_", "-"), **options)
    args = parser.parse_args()
    if args.mode == "schema":
        emit(catalog()[args.operation] if args.operation else catalog())
        return 0
    try:
        if args.mode != "session":
            if args.mode == "call":
                from pathlib import Path
                raw = Path(args.args[1:]).read_text(encoding="utf-8-sig") if args.args.startswith("@") else args.args
                values = json.loads(raw)
            else:
                values = {p: getattr(args, p) for p in signature(args.operation).parameters}
            if not isinstance(values, dict):
                raise ValueError("Arguments require a JSON object")
            if args.operation in OFFLINE:
                emit(EXTRAS[args.operation][0](**values))
                return 0
        if not args.state_dir:
            raise ValueError("--state-dir is required for this operation")
        workbench = Workbench(args.state_dir)
        try:
            if args.mode != "session":
                result = call(workbench, args.operation, values)
                emit(result)
                return int(isinstance(result, dict) and result.get("ok") is False)
            for line in sys.stdin:
                request_id = None
                try:
                    request = json.loads(line)
                    request_id = request.get("id")
                    result = call(workbench, request["operation"], request.get("arguments", {}))
                    emit({"id": request_id, "ok": not (isinstance(result, dict) and result.get("ok") is False), "result": result})
                except Exception as exc:
                    emit({"id": request_id, "ok": False, "error": type(exc).__name__, "message": str(exc), "retry_safe": False})
        finally:
            workbench.close()
    except Exception as exc:
        emit({"ok": False, "error": type(exc).__name__, "message": str(exc), "retry_safe": False})
        return 1
    return 0
