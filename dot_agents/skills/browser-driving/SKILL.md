---
name: browser-driving
description: Reliable browser-harness recipes for viewport setup, tab ownership, resuming browser work, and ChatGPT webpage interaction. Use alongside browser-harness for interactive websites; route chat history and structured data to native readers or APIs, and repeatable application tests to project-local Playwright.
---

# Browser driving

Load the installed `browser-harness` skill before controlling a browser. It owns
connection, input, scrolling, screenshots, and recording mechanics; this companion
owns task state and the call recipes below. Preserve its installation and the
project's Playwright setup.

## Route the task

```text
Chat history / structured data → native reader or API
Interactive website work      → browser-harness + browser-driving
Repeatable application tests  → project-local Playwright
Pencil canvas work            → pencil-workflow
Native application dialogs    → computer-use tools when needed
```

Use a browser for history only when the native reader is unavailable or incomplete.
Reading history does not authorize sending a prompt. For ChatGPT webpage work,
read [references/chatgpt.md](references/chatgpt.md) before interacting.

## Own and resume the target

Serialize control of shared local Chrome across tasks and agents. Different
`BU_NAME` daemon names preserve separate attachments, not separate browsers.
Arrange one controller at a time; if another task holds control, wait or hand off.
Use an already-authorized isolated browser endpoint when isolation is needed.

Keep these fields in the task's **ignored** handoff notes, and verify that the
notes are ignored before saving browser state:

| Field | Save |
| --- | --- |
| Connection | Exact daemon name (`default` when unset); endpoint identity when applicable, excluding credentials |
| Target | Target ID, expected origin, and URL or conversation identity |
| Viewport | Width, height, device scale factor, mobile flag |
| Ownership | Task-created or borrowed, with the before/after target inventory |
| Recording | Exact directory returned by `start_recording()`, or `none`; active/stopped status |
| Last verified state | Timestamp, URL, observed state, next action, and controller/handoff status |

On first entry, inspect `current_tab()` and `list_tabs()` for a verified matching
target. When opening the task's first URL with `new_tab(url)`, compare target IDs
before and after: it can navigate an existing blank tab. Mark a reused target
**borrowed**, even if its URL changed. Only a newly added target is task-created.

On each resume, restore the saved connection selection, list targets, and find
the exact saved ID. Check its expected origin and page identity before attaching,
then `switch_tab(saved_id)` and verify `current_tab()` and the live page identity
again. Verify the viewport and last expected state before input. Treat a mismatch
as unresolved: inspect and resolve the intended target explicitly before acting.

A missing target must stop target-dependent actions. Establish an explicitly
identified replacement (or a fresh task tab when the task permits restarting),
record the new ID and ownership, then verify it. A resume never uses tab order,
`ensure_real_tab()`, or a matching origin alone to choose an arbitrary target.

Cleanup closes only recorded task-created IDs that still exist and still match
the expected page. Borrowed targets, including reused blank tabs, survive.
For borrowed tabs, save prior emulation settings when known and restore changes
on handoff; otherwise clear task-applied overrides and disclose any remaining
navigation or state change. Keep the notes current after navigation and recording
changes, not only at the end.

## Tested call recipes

Verified with browser-harness **0.1.13**. When the installed version changes,
inspect the installed helper signatures before adapting these calls.

```python
cdp("Emulation.setDeviceMetricsOverride",
    width=390, height=844, deviceScaleFactor=1, mobile=True)
print(js("({width: innerWidth, height: innerHeight})"))
print(js("document.body.innerText"))
print(js("(() => ({width: innerWidth, height: innerHeight}))()"))
print(capture_screenshot("/absolute/ignored/evidence/mobile.png"))
```

CDP method parameters are keyword arguments. The installed signature is
`cdp(method, session_id=None, _response_timeout=..., **params)`; a dictionary
passed second becomes the session identifier. The historical diagnostic
`Message may have string 'sessionId' property` means that value was not a string.
Correct the call by passing `width=...`, `height=...`, and other parameters as
keywords; reserve `session_id` for an actual session identifier.

`js(expression, target_id=None)` evaluates JavaScript. An arrow function such as
`() => document.body.innerText` returns a function rather than the requested
text. Use the expression directly or invoke the function, as above. Parenthesize
object literals. Check actual values, not only successful command exit codes.

For mobile pages, a viewport declaration such as
`<meta name="viewport" content="width=device-width, initial-scale=1">` is needed
for CSS `innerWidth` to match the device width. Verify both the reported viewport
and PNG dimensions; preserve project language and right-to-left defaults.

## Recovery and recordings

For connection failures, read upstream [connection guidance](https://github.com/browser-use/browser-harness/blob/main/interaction-skills/connection.md).
For a timed-out scroll, read upstream [scrolling guidance](https://github.com/browser-use/browser-harness/blob/main/interaction-skills/scrolling.md)
and follow its bounded retry, then verify the page or container scroll position.
If current upstream guidance differs from the installed skill, check the installed
helper signatures and use the supported background recovery. Foregrounding a tab
requires a user-requested visible switch. Stop and report the limitation if the
bounded recovery fails; custom JavaScript scrolling is not a substitute.

When recording is requested, use the installed skill's recording workflow. Save
the exact directory returned by `start_recording()` immediately. On resume,
compare `recording_dir()` with the saved active directory before recorded actions;
resolve a mismatch explicitly. `stop_recording()` must return that same directory.
Use upstream [video guidance](https://github.com/browser-use/browser-harness/blob/main/interaction-skills/make-video.md)
for export and verification. Resume evidence uses the saved path, never
`recordings --latest`.
