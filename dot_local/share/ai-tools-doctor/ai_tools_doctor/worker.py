"""Probe worker that emits bounded, structured events and discards server stderr."""
from __future__ import annotations

import json
import os
import sys
import time

import anyio

from . import smoke

CONNECT_SECONDS = 20
SMOKE_SECONDS = 10
MAX_PAGES = 50
EMITTED: set[str] = set()
HTTP_STATUSES: list[int] = []   # Response bodies and headers are never retained.
STARTED = 0.0


def emit(stage: str, outcome: str, reason_code: str, **facts) -> None:
    EMITTED.add(stage)
    event = {"stage": stage, "outcome": outcome, "reason_code": reason_code,
             "elapsed_ms": max(0, int((time.monotonic() - STARTED) * 1000))}
    event.update(facts)
    print(json.dumps(event), flush=True)


def flatten(exc: BaseException):
    if isinstance(exc, BaseExceptionGroup):
        for inner in exc.exceptions:
            yield from flatten(inner)
    else:
        yield exc
        if exc.__cause__ is not None:
            yield from flatten(exc.__cause__)


def _http_status(value) -> int | None:
    return value if type(value) is int and 100 <= value <= 599 else None


def _protocol_code(leaf: BaseException) -> int | None:
    error = getattr(leaf, "error", None)
    values = (getattr(leaf, "code", None), getattr(error, "code", None),
              error.get("code") if isinstance(error, dict) else None)
    return next((value for value in values if type(value) is int and -32768 <= value <= 65535), None)


def classify_error(exc: BaseException) -> tuple[str, dict]:
    """Classify by exception type and numeric fields; never read exception text."""
    leaves = list(flatten(exc))
    statuses = [_http_status(status) for status in HTTP_STATUSES]
    statuses += [_http_status(getattr(getattr(leaf, "response", None), "status_code", None)) for leaf in leaves]
    status = next((code for code in statuses if code is not None), None)
    protocol = next((code for leaf in leaves if (code := _protocol_code(leaf)) is not None), None)
    if status in (401, 403):
        return "auth_required", {"reason_code": f"http_{status}", "http_status": status,
                                 **({"protocol_code": protocol} if protocol is not None else {})}
    if status is not None:
        return "failed", {"reason_code": "http_error", "http_status": status,
                          **({"protocol_code": protocol} if protocol is not None else {})}
    if any(isinstance(leaf, TimeoutError) for leaf in leaves):
        return "timeout", {"reason_code": "timeout"}
    if any(isinstance(leaf, FileNotFoundError) for leaf in leaves):
        return "failed", {"reason_code": "executable_not_found"}
    if any(isinstance(leaf, PermissionError) for leaf in leaves):
        return "failed", {"reason_code": "permission_denied"}
    if protocol is not None:
        return "failed", {"reason_code": "protocol_error", "protocol_code": protocol}
    if any(isinstance(leaf, ConnectionError) for leaf in leaves):
        return "failed", {"reason_code": "connection_error"}
    return "failed", {"reason_code": "unexpected_failure"}


async def run(req: dict) -> None:
    global STARTED
    EMITTED.clear()
    HTTP_STATUSES.clear()
    STARTED = time.monotonic()
    errlog = open(os.devnull, "w")
    stack_tools = []
    state = {"stage": "connection"}
    # One shared budget for spawn + initialize + every tools/list page (20s for connection/discovery).
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp_types import PaginatedRequestParams
        from mcp.client.stdio import stdio_client

        connect_deadline = anyio.current_time() + CONNECT_SECONDS
        remaining = lambda: max(0.05, connect_deadline - anyio.current_time())
        with anyio.fail_after(CONNECT_SECONDS + SMOKE_SECONDS + 2):   # outer worker backstop
            if req["transport"] == "stdio":
                transport = stdio_client(StdioServerParameters(
                    command=req["command"], args=req["args"], env=req["env"] or None, cwd=req.get("cwd")), errlog=errlog)
            else:
                import httpx2
                from mcp.client.streamable_http import streamable_http_client

                async def record(response):
                    status = _http_status(response.status_code)
                    if status is not None:
                        HTTP_STATUSES.append(status)

                client = httpx2.AsyncClient(headers=req.get("headers") or {}, follow_redirects=False,
                                            event_hooks={"response": [record]})
                transport = streamable_http_client(req["url"], http_client=client)
            async with transport as streams:
                read, write = streams[0], streams[1]
                async with ClientSession(read, write) as session:
                    with anyio.fail_after(remaining()):
                        await session.initialize()
                    emit("connection", "passed", "initialize_succeeded")
                    state["stage"] = "discovery"
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
                        emit("discovery", "failed", "pagination_limit", pages_count=pages)
                        return
                    if not stack_tools:
                        emit("discovery", "unverified", "zero_tools", tools_count=0, pages_count=pages)
                        return
                    emit("discovery", "passed", "tools_discovered", tools_count=len(stack_tools), pages_count=pages)
                    state["stage"] = "smoke"
                    kind = smoke.kind_for(req["server"], req.get("command"), req["args"])
                    if not req.get("smoke") or kind is None:
                        emit("smoke", "skipped", "smoke_not_available")
                        return
                    tool, arguments, _reason = smoke.plan(kind, req["server"], stack_tools, req["args"],
                                                          req.get("restrictions") or {})
                    if tool is None:
                        emit("smoke", "unverified", "smoke_tool_unavailable")
                        return
                    try:
                        with anyio.fail_after(SMOKE_SECONDS):
                            res = await session.call_tool(tool, arguments)
                    except TimeoutError:
                        emit("smoke", "timeout", "timeout")
                        return
                    if res.is_error:
                        emit("smoke", "failed", "smoke_tool_error")
                        return
                    text = "".join(getattr(c, "text", "") or "" for c in res.content)
                    if smoke.judge(kind, text):
                        emit("smoke", "failed", "smoke_response_invalid")
                        return
                    emit("smoke", "passed", "smoke_passed")
    except TimeoutError:
        if state["stage"] not in EMITTED:
            emit(state["stage"], "timeout", "timeout")
    except BaseException as exc:  # noqa: BLE001 - safe classification; never serialize exception text
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        outcome, facts = classify_error(exc)
        if state["stage"] not in EMITTED:
            emit(state["stage"], outcome, facts.pop("reason_code"), **facts)
    finally:
        errlog.close()


def main() -> int:
    req = json.loads(sys.stdin.read())
    anyio.run(run, req)
    emit("done", "passed", "worker_finished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
