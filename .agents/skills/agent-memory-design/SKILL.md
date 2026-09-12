---
name: agent-memory-design
description: >
  Guidance for designing and reviewing the memory subsystem of this
  multi-agent, multi-channel chat platform: working/session/long-term memory
  tiers, per-user and per-channel isolation, shared vs agent-specific
  memory, retrieval strategy, and lifecycle (TTL, pruning, deletion). Use
  when building or reviewing conversation history storage, user profiles,
  RAG/vector memory, or how context is assembled and shared across agents.
---

# Agent Memory Design

Memory is the highest-risk shared state in a multi-agent system: get the
isolation or retrieval wrong and one user's data leaks into another's
conversation, or one agent's stale assumption contradicts what another agent
just told the user.

## When to Use

- Designing or changing how conversation history is stored or loaded.
- Adding a long-term user profile, preference store, or RAG/vector memory.
- Any change to how context is assembled before an LLM call, or how memory
  is shared between agents.
- Reviewing a bug report about the wrong user's info showing up, or an agent
  "forgetting" something it should know.

## Step 1 — Name the Memory Tiers

Be explicit about which tier a piece of state belongs to; don't let them
blur together in one undifferentiated "context blob":

| Tier | Scope | Lifetime | Example |
|---|---|---|---|
| Working memory | current turn | one LLM call | the message just received + immediate tool results |
| Session memory | one conversation thread | until session ends/times out | recent turns in this WhatsApp/web thread |
| Long-term memory | one user, across sessions and channels | persists until deleted/expired | stated preferences, past order history |
| Shared knowledge | not user-specific | stable, versioned | product docs, FAQ, policies used for RAG |

If a feature request doesn't say which tier it needs, ask or default to the
narrowest one that satisfies the requirement — don't promote something to
long-term memory "just in case".

## Step 2 — Enforce Isolation Keys

- Every session/long-term memory read or write must be keyed by at least
  `(user_id)`, and session memory additionally by `(channel, thread_id)`.
- The same human across two channels (e.g., WhatsApp and web) is a
  **product decision**, not a default: only merge their memory under a
  unified `user_id` if there's an explicit identity-linking step (verified
  login, phone match, etc.) — never merge on a guessed heuristic.
- An agent should only be able to query the memory scope it's authorized
  for. A specialized agent that shouldn't see billing history shouldn't have
  a code path that can query it, even indirectly through a shared "get user
  context" call that returns everything.

## Step 3 — One Source of Truth

Multiple agents must read/write through a single memory service/interface
backed by one store, not keep their own local copies that can diverge.
When reviewing code, flag any agent that caches user state in its own
in-memory dict across turns instead of going through the shared store —
that's how agents end up disagreeing about what the user already said.

## Step 4 — Retrieval Strategy

- Don't inject unbounded history into the prompt. Use recency (last N turns)
  plus relevance (embedding search over older history/long-term memory) and
  cap total tokens injected.
- Summarize/compact old turns instead of dropping them silently or keeping
  them verbatim forever — note in code/comments what summarization policy is
  used so behavior is predictable.
- When multiple agents each pull context for the same turn, make sure
  they're not each independently re-summarizing or re-querying the same
  data in inconsistent ways — prefer computing shared context once per turn.

## Step 5 — Lifecycle and Privacy

- Define a TTL or pruning policy for session memory; don't let threads grow
  unbounded.
- Long-term memory needs an explicit deletion path (user-initiated "forget
  me" or admin/GDPR-style request) that actually removes data from the
  store and any derived vector index, not just the primary record.
- Anything that looks like a secret, credential, or highly sensitive PII
  should not be persisted into long-term/vector memory verbatim — flag it
  if you see it happening.

## Failure Modes to Watch For

- Context window/cost blowing up from unbounded history injection.
- Cross-user or cross-channel data leakage from a missing isolation key.
- Agents silently disagreeing because each holds a stale local copy of user
  state instead of reading the shared store.
- Vector memory that never expires, quietly accumulating stale or deleted-in-
  primary-store data.

See also [[chat-security-review]] for the security/PII angle on this same
subsystem.
