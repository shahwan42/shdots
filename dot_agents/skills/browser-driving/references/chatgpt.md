# ChatGPT webpage interaction

Use this branch only when the task requires the ChatGPT website. Native chat
readers remain the first route for history. Load the installed `browser-harness`
skill and retain the companion's verified target and ownership notes.

## Identify the destination

Verify the requested account or workspace through visible account information,
then verify the requested conversation through its URL, title, and relevant
messages. A ChatGPT origin or familiar title alone is insufficient. If the
account or conversation is ambiguous, ask for the missing identity before input.
Follow the installed skill's authentication boundary for login walls.

## Prepare and submit

Sending a prompt requires explicit user authorization. A history-reading task
ends with the requested information; it does not send a follow-up prompt.

For an authorized prompt, locate the live composer in the accessibility tree,
enter the requested text with page-appropriate input, and read its contents back
from the actual textarea or contenteditable element. Compare the complete string
with the requested text, including Arabic, line breaks, punctuation, and spaces.
Verify the destination again and any requested attachments before submitting.
Resolve differences before clicking Send; do not rely on a screenshot of a
truncated composer or a successful typing command.

After submission, verify that the conversation contains the exact outgoing
message. Wait for the response to finish using the page's generation indicators
and final response state, with a bounded timeout appropriate to the request.
Record completion or the observed failure. If submission is uncertain, inspect
the conversation before retrying so the prompt is not sent twice. A timeout does
not authorize a duplicate submission.

## Recover

Use upstream [connection](https://github.com/browser-use/browser-harness/blob/main/interaction-skills/connection.md),
[scrolling](https://github.com/browser-use/browser-harness/blob/main/interaction-skills/scrolling.md),
and [recording/video](https://github.com/browser-use/browser-harness/blob/main/interaction-skills/make-video.md)
instructions for those mechanics. Resume the saved target and exact recording
directory under the companion's rules. Resolve unexpected navigation or account
changes before resuming input.
