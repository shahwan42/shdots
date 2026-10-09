"""Fixture MCP stdio server with selectable failure modes (JSON-RPC over stdio, no SDK)."""
import json
import os
import subprocess
import sys
import time

mode = sys.argv[1] if len(sys.argv) > 1 else "ok"
pidfile = os.environ.get("FIXTURE_PIDFILE")
SECRET = os.environ.get("FIXTURE_STDERR_SECRET")

if SECRET:
    print(f"startup diagnostic token={SECRET} connecting to postgresql://app:{SECRET}@db.internal/x", file=sys.stderr, flush=True)
if mode == "hang-children":
    child = subprocess.Popen(["sleep", "300"], start_new_session=True)
    if pidfile:
        open(pidfile, "w").write(str(child.pid))
    time.sleep(300)
if mode == "hang-init":
    time.sleep(300)


def tool(name, props=None, required=None):
    return {"name": name, "description": name,
            "inputSchema": {"type": "object", "properties": props or {}, "required": required or []}}


TOOLS = [tool("list_projects", {"limit": {"type": "integer", "minimum": 1}}), tool("other")]
if mode == "zero-tools":
    TOOLS = []
if mode == "no-smoke-tool":
    TOOLS = [tool("other")]


def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


for line in sys.stdin:
    message = json.loads(line)
    method, ident = message.get("method"), message.get("id")
    if ident is None:
        continue
    if mode == "slow-both" and method in ("initialize", "tools/list"):
        time.sleep(12)
    if method == "initialize":
        if mode == "initialize-error":
            message = os.environ.get("FIXTURE_ERROR_TEXT", "synthetic-provider-message")
            send({"jsonrpc": "2.0", "id": ident,
                  "error": {"code": -32077, "message": message}})
            continue
        send({"jsonrpc": "2.0", "id": ident, "result": {
            "protocolVersion": message["params"]["protocolVersion"], "capabilities": {"tools": {}},
            "serverInfo": {"name": "fixture", "version": "1"}}})
    elif method == "tools/list":
        cursor = (message.get("params") or {}).get("cursor")
        if mode == "malformed-tools":
            send({"jsonrpc": "2.0", "id": ident, "result": {"tools": "not-a-list"}})
        elif mode == "paginated":
            if not cursor:
                send({"jsonrpc": "2.0", "id": ident, "result": {"tools": TOOLS[:1], "nextCursor": "p2"}})
            else:
                send({"jsonrpc": "2.0", "id": ident, "result": {"tools": TOOLS[1:]}})
        else:
            send({"jsonrpc": "2.0", "id": ident, "result": {"tools": TOOLS}})
    elif method == "tools/call":
        if mode == "hang-call":
            time.sleep(300)
        is_error = mode == "iserror"
        text = "boom" if is_error else "projects: 1 project-list-body-that-must-not-be-stored"
        send({"jsonrpc": "2.0", "id": ident, "result": {"content": [{"type": "text", "text": text}], "isError": is_error}})
    else:
        send({"jsonrpc": "2.0", "id": ident, "result": {}})
