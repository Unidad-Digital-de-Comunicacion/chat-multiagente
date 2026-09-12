---
name: multichannel-chat-ux-design
description: >
  Interaction and UX design guidance for a chat product delivered
  consistently across multiple channels (web widget, WhatsApp, Telegram,
  Slack, email, etc.) and handled by multiple specialized agents. Use when
  designing conversation flows, agent hand-off/routing, persona and tone,
  error/fallback messaging, or channel-specific UI constraints for
  chat-multiagente. Not for visual mockup/artifact creation — pair with the
  `design` skill for that.
---

# Multichannel, Multi-Agent Chat UX Design

The two things that make this product's UX hard are (1) the same
conversation experience must degrade gracefully across channels with very
different capabilities, and (2) more than one agent may answer in the same
thread, which risks confusing or inconsistent-feeling responses if not
designed deliberately.

## When to Use

- Designing a new conversation flow, intent, or routing rule.
- Adding a new channel adapter (its constraints shape what the conversation
  can look like).
- Deciding how/when to disclose agent hand-off to the user.
- Designing error, timeout, or "I don't understand" fallback messaging.

## Step 1 — Know Each Channel's Constraints

Before designing a flow, check what the target channel(s) actually support:

| Capability | Web widget | WhatsApp | Telegram | Slack | Email |
|---|---|---|---|---|---|
| Rich buttons/quick replies | yes | limited | yes | yes | no |
| Typing indicator | yes | yes | yes | yes | no (async) |
| Threading | optional | no (linear) | yes | yes | yes (subject) |
| Message length | flexible | capped | capped | capped | flexible |
| Read receipts | maybe | yes | yes | yes | no |

Design the flow for the *lowest common denominator* of the channels it must
support, then layer richer affordances (buttons, cards) as progressive
enhancement where the channel allows it — never make a flow depend on a
capability a supported channel lacks.

## Step 2 — Design Hand-off as a Visible Event

When the orchestrator routes a conversation to a different specialized
agent, the user should get a lightweight, honest signal — not a silent
persona swap and not a jarring "Transferring you to Agent 7" system-message
tone. Keep one consistent voice/brand for the whole system by default;
only surface hand-off explicitly when the change is meaningful to the user
(e.g., moving from bot to a human, or between clearly distinct capabilities
the user asked for).

## Step 3 — Design for Latency Honestly

Multi-agent chains (router → specialist → tool call → response) take longer
than a single LLM call. For channels that support it, show a typing/
"processing" indicator before the round-trip completes; for channels that
don't (email), set expectations in the copy ("we'll reply shortly") instead
of leaving silence. Never let a user wonder if their message was received.

## Step 4 — Design Fallbacks, Not Dead Ends

Every flow needs an explicit answer to "what happens when this fails?":

- Agent/tool timeout or error → apologize plainly, offer retry or a
  narrower question, never expose raw error text to the user.
- Ambiguous routing (orchestrator can't tell which agent should handle it)
  → ask one clarifying question rather than guessing silently.
- Repeated failure on the same request → offer an escalation path (human
  handoff, alternate channel, support contact) instead of looping forever.

## Step 5 — Keep Tone Consistent, Adapt Format

The brand voice/persona should be the same everywhere; only the *format*
adapts per channel (e.g., shorter sentences and no markdown tables over
WhatsApp, richer formatting on web/Slack). If different agents have
distinct sub-personas, document when that's intentional vs. an inconsistency
to fix.

## Step 6 — Accessibility Baseline

- Never encode meaning in emoji/color alone — pair with plain text.
- Web widget: focus management, keyboard navigation, and screen-reader
  labels for messages and quick-reply buttons.
- Keep a plain-text fallback for every rich message (buttons/cards) for
  channels or accessibility tools that can't render it.

## Review Checklist for a New Flow

1. Does it work on the narrowest supported channel without breaking?
2. Is hand-off (if any) disclosed appropriately, not silent or jarring?
3. Is there a visible signal during multi-step/slow processing?
4. Does every failure path leave the user with a next action?
5. Is tone consistent with the rest of the system?
