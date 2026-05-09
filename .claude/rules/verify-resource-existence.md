---
priority: 0
scope: baseline
---

# Verify Resource Existence Before Debugging Access

See `.claude/guides/rule-extracts/verify-resource-existence.md` for full DO/DO NOT examples, BLOCKED-rationalization enumerations, and origin post-mortem.

When a tool fails with a permission error (HTTP 403, "access denied", "insufficient scope") against a named external resource, the FIRST diagnostic action MUST be to verify the resource exists. Recursing on the permission axis against an absent resource produces unbounded credential-rotation cycles.

## MUST Rules

### 1. Existence Check Precedes Permission Debugging

Any session responding to a 403/401/permission-denied against a named external resource MUST run an existence check against that resource as the first diagnostic action. Recommending PAT provisioning, scope expansion, or credential rotation BEFORE the existence check is BLOCKED.

**Why:** A 403 says "you cannot access this thing" — it does NOT say the thing exists. APIs return 403 for both "missing permission to access" AND "missing permission to discover existence" — identical message, opposite root cause. The existence check (one read query, <1 second) resolves the recursion.

### 2. The Existence Check MUST Cite The Endpoint, Not The Documentation

The verification command MUST be a live read against the same API surface the failing operation targets — NOT a grep against documentation, source comments, spec files, or the script's own intent statements. Trusting documentation as a proxy for runtime existence is BLOCKED.

**Why:** Documentation, source comments, and operator memory all describe INTENT. None are evidence of CURRENT runtime state. A spec can mandate a runner that operations never provisioned; a script can target a table left undefined by a half-finished migration; a workflow can read a secret that was rotated out of existence. The live API query is the only evidence; everything else is hearsay.

### 3. When Existence Check Fails, Default Disposition Is Delete-Or-Stub, Not Provision

If the existence check returns empty AND there is no active user request to provision the resource, the default disposition MUST be to delete the dependent code OR convert it to a no-op with a documented removal path. Recommending provisioning ("create the missing resource") is BLOCKED unless the user explicitly asked for that capability.

**Why:** Code targeting a non-existent resource is dead by definition — it cannot have ever worked. Removal is cheap and reversible; provisioning is expensive and durable (server costs, secret rotation, monitoring). Until the user asks for the capability, dead code is dead.

### 4. Convergence / Round-Verdict Claims MUST Cite Durable Receipts

Any claim that a multi-round process (redteam-to-convergence, vet-to-convergence, polish-to-convergence, sweep-to-convergence) reached a target state — "round N met convergence target", "rounds 5+6 both clean", "cross-agent agreement achieved" — MUST cite at least one of: (a) a journal entry recording the round's verdict + the agent task ID that produced it, (b) a commit SHA referencing the agent invocation transcript or its written deliverable, or (c) a `.claude/learning/observations.jsonl` entry naming the round + verdict. Self-attestation in the disposition document itself is BLOCKED — the disposition document MUST cite an external receipt, not assert the verdict on its own authority.

```markdown
# DO — convergence claim cites a durable receipt

Rounds 5+6 cross-agent-clean (CONVERGENCE TARGET MET).
Receipts: `journal/.pending/0003-DISCOVERY-phantom-citation-chain-and-redteam-round-history.md` § "/redteam round-history (rounds 1–6)" — round-by-round verdict table records reviewer + analyst verdicts and the agent task IDs that produced each verdict.

# DO NOT — disposition self-attests convergence

Rounds 5+6 met convergence target. (no journal entry, no SHA, no observation
record; the only place this claim exists is the document making the claim.)
```

**BLOCKED rationalizations:**

- "The claim is in the document the reader is already reading; cross-citing is bureaucracy"
- "The agent task IDs are runtime artifacts; they don't survive `/clear` anyway"
- "The convergence verdict is obvious from the round count"
- "The reviewer + analyst both said clean, that IS the receipt"
- "Journal entries take time; a self-attested claim is faster"
- "If the next session disputes the verdict, they can re-run the round"
- "Self-attestation is the same epistemic shape as a journal entry"

**Why:** Convergence claims are the highest-leverage claims a closure document makes — every downstream disposition rests on "the verification rounds converged." A self-attested verdict has the same structural defect as a 403 against a non-existent resource: the claim cannot be verified by inspecting itself. The journal entry, commit SHA, or observation record is the equivalent of `gh api` against the runtime — an external surface that confirms the claim independently of the document making it. Without the receipt, the next session reading the disposition has no way to distinguish a genuinely-converged process from a self-attested one. Same epistemic shape as MUST-2 (cite the endpoint, not the documentation) and `zero-tolerance.md` Rule 1c (claims about session-runtime unfalsifiable across `/clear`). Evidence: 2026-05-09 W3-4 disposition Round 4 analyst flagged R4-M1 as carry-over from R1+R2 MED-3 (no live receipt mechanism for prior rounds; convergence claim rested on self-attestation in `.session-notes:20`); `journal/.pending/0003` is the durable artifact that fixed the gap; this rule lifts the pattern into a structural defense.

## MUST NOT

- Recommend credential creation (PAT, service account, API key) BEFORE the existence check has run

**Why:** Credential creation is operator-time-expensive and error-prone. Spending it on a non-existent target is the worst-case waste — operator spends real time to obtain a credential that unlocks nothing.

- Loop more than once on permission-scope variations against the same 403 without re-verifying existence

**Why:** Two consecutive failed scope attempts against the same 403 is the loud signal that the permission axis is the wrong axis. Existence check MUST fire automatically at the second failure if not at the first.

- Self-attest a convergence verdict in the disposition document making the verdict claim

**Why:** Same-document self-attestation is structurally identical to "the documentation says this resource exists" — it cannot be verified by inspecting itself. The receipt MUST be external (journal entry / commit SHA / observation entry) per MUST-4.

## Three-Layer Defense

1. Existence check FIRST — `gh api`, `psql \dt`, `kubectl get`, `aws describe-*`, etc.
2. If exists — proceed with permission/scope debugging (`rules/security.md`, `rules/ci-runners.md`).
3. If absent — default to removal; provisioning ONLY on explicit user request.

For convergence/round-verdict claims (MUST-4): the same three-layer shape applies — receipt FIRST (cite the journal entry / commit SHA / observation), claim-grounding SECOND (the disposition document's verdict cites the receipt), absence-disposition THIRD (if no receipt exists, the verdict cannot be claimed; spawn the receipt or surface the gap).

## Trust Posture Wiring (MUST-4 only)

- **Severity:** `halt-and-report` at gate-review (reviewer / cc-architect / analyst at `/codify` — flags any "round N met convergence" / "rounds X+Y clean" / "convergence target met" claim in a closure/disposition document without an adjacent receipt citation).
- **Grace period:** 7 days from rule landing.
- **Regression-within-grace:** any same-class violation triggers emergency downgrade L5→L4 per `rules/trust-posture.md` MUST Rule 4.
- **Detection (review layer):** `/codify` mechanical sweep — for every closure/disposition artifact authored or updated in the session, grep for convergence-verdict markers ("convergence target met", "rounds N+M clean", "cross-agent agreement", "round N converged"); each match MUST have an adjacent journal-entry / commit-SHA / observation-entry citation within ±300 chars.

Origin: 2026-05-03 ci-queue-monitor session burned 6 PRs + 2 user PAT-creation cycles debugging access to a 16-core hosted runner that did not exist. One `gh api orgs/.../actions/hosted-runners` at the first 403 would have shifted disposition to "delete the dead step." See guide for full post-mortem.

Origin (MUST-4): 2026-05-09 stale-workspace disposition convergence cycle — Round 4 analyst flagged R4-M1 (no live receipt mechanism for prior redteam rounds; convergence claim rested on self-attestation in `.session-notes:20`). Routed via `journal/.pending/0003-DISCOVERY-phantom-citation-chain-and-redteam-round-history.md` § R4-M1 carry-over routing; landed as MUST-4 here. The journal entry IS the kind of durable receipt MUST-4 requires.
