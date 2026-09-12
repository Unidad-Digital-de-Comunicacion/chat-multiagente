---
name: chat-security-review
description: >
  Security review checklist and threat-model guidance for this multi-agent,
  multi-channel chat platform (chat-multiagente). Use before shipping code
  that touches channel webhooks (WhatsApp, Telegram, Slack, web widget,
  email, etc.), inter-agent message/tool-call passing, secrets, LLM API
  calls, or stored user data. Covers webhook trust, prompt-injection between
  agents, tool/function-calling safety, rate limiting, and PII handling.
  Do NOT use for unrelated general-purpose security questions outside this
  project's architecture.
---

# Chat Platform Security Review

This skill reviews security for a system with **multiple external channels**
feeding **multiple cooperating agents** that can call tools and share memory.
That combination creates threat surface that a single-service app doesn't
have: every channel is an untrusted entry point, and every agent-to-agent
message is a potential injection vector into the next agent's tool calls.

## When to Use

- Adding or changing a channel integration (webhook receiver, bot API, email
  ingest, web widget endpoint).
- Adding/changing an agent's tool access, function-calling schema, or the
  orchestrator's routing logic.
- Touching secrets, API keys, or how conversation/user data is stored.
- Before merging any change a user asked you to security-review.
- Not for: generic code style, unrelated business logic with no external
  input or privileged action.

## Step 1 — Map the Untrusted Entry Points

For this architecture, list every channel adapter and classify it:

| Channel | Ingress mechanism | Authenticity check | Notes |
|---|---|---|---|
| WhatsApp/Telegram/Slack | inbound webhook | HMAC/signature header verified? | replay window, timestamp check |
| Web widget | HTTP/WS from browser | session/CSRF token? | anonymous vs authenticated user |
| Email | inbound parse webhook | SPF/DKIM/provider signature checked? | attachments = untrusted files |

Every inbound webhook payload is **untrusted input** even though it comes
from a "trusted" provider — verify the provider's signature/secret on every
request, reject on failure, and never trust a `from`/`sender` field in the
payload body alone.

## Step 2 — Trace Inter-Agent Trust Boundaries

In a multi-agent design, the output of Agent A often becomes input to
Agent B's prompt or, worse, an argument to a tool call. Treat this as a
trust boundary crossing:

- Does any agent's free-text output get concatenated into another agent's
  system/tool-selection prompt without delimiting it as data? That's a
  prompt-injection path — a malicious end user can steer Agent A's output to
  hijack Agent B.
- Does the orchestrator ever pass a user-supplied string directly as a tool
  argument (file path, shell command, SQL fragment, URL to fetch) without
  validation? Flag it.
- Are there tools with side effects (send message, call external API, write
  to DB, spend money) reachable from agents whose input traces back to an
  untrusted channel? Those need an allowlist of permitted actions and,
  for irreversible/high-impact ones, an explicit confirmation step.

## Step 3 — Secrets and Credentials

- One credential per channel/provider and per LLM API key; never a single
  shared key reused everywhere.
- Confirm secrets are read from environment/secret manager, never
  hardcoded, never logged (including in error stack traces or LLM prompt
  logs), and never echoed back to a user by an agent.
- Check `.gitignore` covers `.env*` and any local credential files before
  a commit that adds channel config.

## Step 4 — Abuse, Cost, and Loop Control

Multi-agent chains can amplify cost and blast radius of abuse:

- Per-user and per-channel rate limiting on inbound messages.
- A hard cap on inter-agent hops/recursion per user turn (prevent infinite
  agent-to-agent delegation loops burning LLM budget).
- Cost ceilings or alerts on LLM API spend per user/time window.

## Step 5 — Data Handling and PII

- Conversation history and any user profile data: encrypted at rest,
  access-scoped so one user's data is never retrievable in another user's
  context (see [[agent-memory-design]] for isolation rules).
- Minimize retained PII; if a channel exposes phone numbers/emails, document
  why they're stored and for how long.
- Provide (or flag the absence of) a deletion/"forget me" path.

## Step 6 — Output Sanitization

- If any channel renders HTML/Markdown from agent output (web widget,
  email), sanitize before rendering to prevent injection into the channel UI.
- Never let an agent's response include raw secrets, internal system
  prompts, or other users' data even if asked to "repeat everything you know".

## Report Format

When reporting findings, rank by exploitability given this project's actual
deployment (is the channel public-facing? does the tool have side effects?),
not by abstract severity. For each finding give: file/location, the
untrusted-input path that reaches it, and the concrete failure scenario.
