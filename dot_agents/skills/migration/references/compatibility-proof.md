# Compatibility proof

Use when two versions of a reader or writer can touch the same data: a rollout
that overlaps, a runtime rollback, a cached older client, or a stored receipt
read by newer code. Skip for changes nobody reads across versions.

```text
Supported behavior
    → relevant version pair and invariant
    → selected test seam
    → retained result for those exact versions
    → stated limits and unresolved gaps
```

## 1. State the claim before implementing

Write it down; keep product decisions in their existing authority.

- **Readers and writers** that cross versions, including clients and jobs.
- **Stored and wire formats** that change: schema, API bodies, history enums,
  request identity (idempotency keys, receipts), configuration. Cover only the
  ones this change touches.
- **Version window:** which older version is supported (usually the immediately
  preceding runtime) and which are not.
- **Identities:** candidate and baseline commit SHAs. The baseline the local gate
  uses may be a stack parent, not the live predecessor. Name the live predecessor
  separately and mark it unverified unless established within authorized scope.
- **Preservation invariants:** facts that must survive an older writer (for
  example, a newer field an older correction must not erase).
- **Rollback action:** what is reverted (runtime) and what is not (data stays
  migrated forward; no automatic down-migration).
- Distinguish **omitted** value, explicit `null`, default, and unsupported field
  wherever behavior differs. An older request that omits a field is not an
  explicit clear.

## 2. Pick the cheapest public seam per claim

Populated migration test, API call, contract parse, client adapter, or browser
interaction. Reuse the existing test that owns the seam; extend it instead of
adding a parallel one.

For a relevant change, establish each stage:

1. Older runtime keeps operating while the migration runs (and migration reruns).
2. Candidate operates over older data.
3. Candidate writes succeed.
4. Older runtime reads and corrects data holding newer facts.
5. Candidate resumes and presents the preserved facts correctly.

Check **storage**, not only returned values, when an older writer could erase
newer facts. A projected JSON comparison proves equivalence of shared fields
only; say so. Claim legacy-client parsing only when the actual older contract, or
a specifically justified compatibility test, ran.

## 3. Record the result for exact versions

A proof names: baseline and candidate SHAs, artifact checksums, fixture or
rehearsal fingerprint, platform, assertions exercised, result location, and gaps.
Keep these classes apart and never promote one to another:

| Class | Meaning |
|---|---|
| Source-observed | Assertion exists in code; not run for these versions |
| Historical report | A past session says it passed; not proof today |
| Current executed pass | Ran against the named versions, result retained |
| Failure / blocked | Report the exact limit; do not substitute an unrelated pass |

Runtime rollback, backup restore, and cached-client updating are different
operations with different proofs. One does not establish another.
