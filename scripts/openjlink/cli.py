import argparse
import inspect
import json
import sys
import types
import typing
from pathlib import Path
from openjlink import __version__
from openjlink.api import EXTRAS, OFFLINE, call, catalog, signature
from openjlink.compact import compact_result, compact_schema
from openjlink.session import Workbench


def emit(value, compact=False):
    kwargs = {"separators": (",", ":")} if compact else {}
    print(json.dumps(value, ensure_ascii=False, allow_nan=False, **kwargs), flush=True)


def _iter_requests(batch_arg):
    if batch_arg is None:
        for line in sys.stdin:
            yield None, line
        return
    raw = sys.stdin.read() if batch_arg == "-" else Path(batch_arg).read_text(encoding="utf-8-sig")
    if raw.lstrip().startswith("["):
        items = json.loads(raw)
        if not isinstance(items, list):
            raise ValueError("Batch input requires a JSON array or JSONL")
        for index, item in enumerate(items, 1):
            yield index, item
        return
    for index, line in enumerate((ln for ln in raw.splitlines() if ln.strip()), 1):
        yield index, line


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
    compact_help = "Omit repeated hashes, timestamps, and boilerplate prose"
    parser = argparse.ArgumentParser(prog="openjlink")
    parser.add_argument("--version", action="version", version="OpenJlink " + __version__)
    parser.add_argument("--state-dir", help=state_help)
    parser.add_argument("--compact", action="store_true", default=False, help=compact_help)
    sub = parser.add_subparsers(dest="mode", required=True)
    schema = sub.add_parser("schema")
    schema.add_argument("--compact", action="store_true", default=argparse.SUPPRESS, help=compact_help)
    schema.add_argument("operation", nargs="?", choices=list(catalog()))
    single = sub.add_parser("call")
    single.add_argument("--state-dir", default=argparse.SUPPRESS, help=state_help)
    single.add_argument("--compact", action="store_true", default=argparse.SUPPRESS, help=compact_help)
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
    session_parser.add_argument("--compact", action="store_true", default=argparse.SUPPRESS, help=compact_help)
    session_parser.add_argument("--batch", default=None, help="JSON array or JSONL file path (or - for stdin)")
    session_parser.add_argument("--stop-on-error", action="store_true", default=False, help="Stop batch on first error and exit 1")
    for name, info in catalog().items():
        direct = sub.add_parser(name.replace("_", "-"), help=info["description"])
        direct.set_defaults(operation=name)
        direct.add_argument("--state-dir", default=argparse.SUPPRESS, help=state_help)
        direct.add_argument("--compact", action="store_true", default=argparse.SUPPRESS, help=compact_help)
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
        data = catalog()[args.operation] if args.operation else catalog()
        if args.compact:
            data = compact_schema(data, args.operation)
        emit(data, compact=args.compact)
        return 0
    try:
        if args.mode != "session":
            if args.mode == "call":
                raw = Path(args.args[1:]).read_text(encoding="utf-8-sig") if args.args.startswith("@") else args.args
                values = json.loads(raw)
            else:
                values = {p: getattr(args, p) for p in signature(args.operation).parameters}
            if not isinstance(values, dict):
                raise ValueError("Arguments require a JSON object")
            if args.operation in OFFLINE:
                result = EXTRAS[args.operation][0](**values)
                if args.compact:
                    result = compact_result(args.operation, result)
                emit(result, compact=args.compact)
                return 0
        if not args.state_dir:
            raise ValueError("--state-dir is required for this operation")
        workbench = Workbench(args.state_dir)
        try:
            if args.mode != "session":
                result = call(workbench, args.operation, values)
                failed = isinstance(result, dict) and result.get("ok") is False
                if args.compact:
                    result = compact_result(args.operation, result)
                emit(result, compact=args.compact)
                return int(failed)
            had_error = False
            for default_id, item in _iter_requests(args.batch):
                request_id = default_id
                try:
                    request = json.loads(item) if isinstance(item, str) else item
                    if not isinstance(request, dict):
                        raise ValueError("Request must be a JSON object")
                    request_id = request.get("id", default_id)
                    operation = request["operation"]
                    result = call(workbench, operation, request.get("arguments", {}))
                    ok = not (isinstance(result, dict) and result.get("ok") is False)
                    if args.compact:
                        result = compact_result(operation, result)
                    emit({"id": request_id, "ok": ok, "result": result}, compact=args.compact)
                except Exception as exc:
                    ok = False
                    emit({"id": request_id, "ok": False, "error": type(exc).__name__, "message": str(exc), "retry_safe": False}, compact=args.compact)
                if not ok:
                    had_error = True
                    if args.stop_on_error:
                        break
            if args.stop_on_error and had_error:
                return 1
        finally:
            workbench.close()
    except Exception as exc:
        emit({"ok": False, "error": type(exc).__name__, "message": str(exc), "retry_safe": False}, compact=args.compact)
        return 1
    return 0
