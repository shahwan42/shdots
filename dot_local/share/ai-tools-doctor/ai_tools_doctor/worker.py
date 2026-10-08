"""Probe worker: one SDK connection, run as an isolated subprocess.

stdin: one JSON request. stdout: one JSON line per completed stage. The parent
owns this process group and kills it (and its descendants) on timeout.
"""
from __future__ import annotations

import json
import sys
import time

import anyio

from . import smoke

CONNECT_SECONDS = 20
SMOKE_SECONDS = 10
MAX_PAGES = 50


EMITTED: set[str] = set()


def emit(stage: str, outcome: str, detail: str, **extra) -> None:
    EMITTED.add(stage)
    print(json.dumps({"stage": stage, "outcome": outcome, "detail": detail, **extra}), flush=True)


def flatten(exc: BaseException):
    if isinstance(exc, BaseExceptionGroup):
        for inner in exc.exceptions:
            yield from flatten(inner)
    else:
        yield exc
        if exc.__cause__ is not None:
            yield from flatten(exc.__cause__)


HTTP_STATUSES: list[int] = []   # the SDK folds HTTP errors into a generic MCPError; keep the status here


def classify_error(exc: BaseException) -> tuple[str, str]:
    leaves = list(flatten(exc))
    for status in HTTP_STATUSES:
        if status in (401, 403):
            return "auth_required", f"HTTP {status} from server; client-owned authentication needed"
    for leaf in leaves:
        response = getattr(leaf, "response", None)
        status = getattr(response, "status_code", None)
        if status in (401, 403):
            return "auth_required", f"HTTP {status} from server; client-owned authentication needed"
        text = str(leaf)
        if "401" in text and "nauthor" in text:
            return "auth_required", "HTTP 401 Unauthorized"
    if any(isinstance(leaf, TimeoutError) for leaf in leaves):
        return "timeout", "stage exceeded its time budget"
    for leaf in leaves:
        if isinstance(leaf, FileNotFoundError):
            return "failed", "server command not found"
        if isinstance(leaf, PermissionError):
            return "failed", "server command not executable"
    leaf = leaves[-1] if leaves else exc
    return "failed", f"{type(leaf).__name__}: {str(leaf)}"


async def run(req: dict) -> None:
    from mcp import ClientSession, StdioServerParameters
    from mcp_types import PaginatedRequestParams
    from mcp.client.stdio import stdio_client

    errlog = open(req["stderr_path"], "w") if req.get("stderr_path") else sys.stderr
    started = time.monotonic()
    stack_tools = []
    state = {"stage": "connection"}
    # One shared budget for spawn + initialize + every tools/list page (spec: 20s for connection/discovery).
    connect_deadline = anyio.current_time() + CONNECT_SECONDS
    remaining = lambda: max(0.05, connect_deadline - anyio.current_time())
    try:
        with anyio.fail_after(CONNECT_SECONDS + SMOKE_SECONDS + 2):   # outer backstop; stages have own budgets
            if req["transport"] == "stdio":
                transport = stdio_client(StdioServerParameters(
                    command=req["command"], args=req["args"], env=req["env"] or None, cwd=req.get("cwd")), errlog=errlog)
            else:
                import httpx2
                from mcp.client.streamable_http import streamable_http_client
                async def record(response):
                    HTTP_STATUSES.append(response.status_code)
                client = httpx2.AsyncClient(headers=req.get("headers") or {}, follow_redirects=False,
                                            event_hooks={"response": [record]})
                transport = streamable_http_client(req["url"], http_client=client)
            async with transport as streams:
                read, write = streams[0], streams[1]
                async with ClientSession(read, write) as session:
                    with anyio.fail_after(remaining()):
                        init = await session.initialize()
                    state["stage"] = "discovery"
                    emit("connection", "passed",
                         f"initialize ok in {time.monotonic() - started:.1f}s; protocol {init.protocol_version}",
                         server_info=f"{init.server_info.name} {init.server_info.version}")
                    cursor, pages = None, 0
                    while pages < MAX_PAGES:
                        with anyio.fail_after(remaining()):
                            page = await session.list_tools(
                                params=PaginatedRequestParams(cursor=cursor) if cursor else None)
                        stack_tools += list(page.tools)
                        pages += 1
                        cursor = page.next_cursor
                        if not cursor:
                            break
                    if cursor:
                        emit("discovery", "failed", f"tools/list pagination exceeded {MAX_PAGES} pages")
                        return
                    if not stack_tools:
                        emit("discovery", "unverified", "server connected but advertises zero tools", tools=0, pages=pages)
                        return
                    emit("discovery", "passed", f"{len(stack_tools)} tools over {pages} page(s)",
                         tools=len(stack_tools), pages=pages)
                    state["stage"] = "smoke"
                    kind = smoke.kind_for(req["server"], req.get("command"), req["args"])
                    if not req.get("smoke") or kind is None:
                        emit("smoke", "skipped", "no reviewed smoke probe for this server" if kind is None
                             else "smoke not requested")
                        return
                    tool, arguments, reason = smoke.plan(kind, req["server"], stack_tools, req["args"],
                                                         req.get("restrictions") or {})
                    if tool is None:
                        emit("smoke", "unverified", reason)
                        return
                    try:
                        with anyio.fail_after(SMOKE_SECONDS):
                            res = await session.call_tool(tool, arguments)
                    except TimeoutError:
                        emit("smoke", "timeout", f"{tool} exceeded {SMOKE_SECONDS}s")
                        return
                    if res.is_error:
                        emit("smoke", "failed", f"{tool} returned isError=true", tool=tool)
                        return
                    text = "".join(getattr(c, "text", "") or "" for c in res.content)
                    bad = smoke.judge(kind, text)
                    if bad:
                        emit("smoke", "failed", f"{tool}: {bad}", tool=tool)
                        return
                    emit("smoke", "passed", f"{tool} succeeded; response body not retained", tool=tool)
    except TimeoutError:
        if state["stage"] not in EMITTED:
            emit(state["stage"], "timeout",
                 f"{state['stage']} did not complete within its time budget "
                 f"({SMOKE_SECONDS if state['stage'] == 'smoke' else CONNECT_SECONDS}s)")
    except BaseException as exc:  # noqa: BLE001 - classified and reported, never raised
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        outcome, detail = classify_error(exc)
        if state["stage"] not in EMITTED:   # a late shutdown error must not overwrite a recorded result
            emit(state["stage"], outcome, detail)
    finally:
        if errlog is not sys.stderr:
            errlog.close()


def main() -> int:
    req = json.loads(sys.stdin.read())
    anyio.run(run, req)
    emit("done", "passed", "worker finished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
