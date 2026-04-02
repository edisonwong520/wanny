# Wanny Roadmap

[中文版本](./ROADMAP.zh-CN.md)

This roadmap captures the next major directions for Wanny. It is intentionally practical: each area is framed around product value, engineering work, and the capability gaps that still matter most.

## Near Term

### 1. More Devices and More Platforms

- Expand support beyond the current integrations and keep growing the physical-device surface area.
- Prioritize new providers with strong household demand, such as Hisense and other mainstream appliance brands.
- Improve provider normalization so newly added platforms can enter the same `provider -> devices -> control -> memory` pipeline with less custom glue.
- Keep device naming, capabilities, telemetry, and control semantics aligned across brands instead of leaking vendor-native fields into the user experience.

### 2. Test Coverage and Reliability

- Add more end-to-end tests for WeChat flows, device queries, device control, approval flows, and background persistence.
- Strengthen regression coverage for provider adapters, especially token refresh, state parsing, control execution, and capability mapping.
- Expand frontend build and interaction coverage so deployment regressions are caught earlier.
- Introduce clearer reliability gates for “can parse”, “can control”, and “can recover” behaviors before new integrations are considered stable.

### 3. Human-Centered Care

- Turn weather, season, and environmental context into useful suggestions rather than passive status reporting.
- Support recommendations such as whether connected appliances should be adjusted when the weather turns colder, hotter, drier, or more humid.
- Make these suggestions explainable, lightweight, and respectful of user preference instead of noisy or over-automated.
- Continue evolving Wanny from command execution toward daily care and practical companionship.

### 4. Proactive Inspection

- Detect maintenance and risk signals automatically, such as filters that should be replaced, consumables that are running low, or devices whose recent telemetry looks abnormal.
- Start with high-value inspection targets like water dispensers, purification devices, air systems, and other appliances with clear maintenance cycles.
- Push proactive reminders in a way that is traceable, reversible, and easy for the user to confirm or dismiss.

## Mid Term

### 5. Small-Model Semantic Understanding

- Reduce reliance on hard-coded keyword heuristics for intent detection and control matching.
- Use smaller and cheaper models for semantic routing, query classification, entity resolution, and device-intent interpretation.
- Keep heuristic fallbacks where they still improve safety, but move primary understanding toward model-driven semantics.
- Build a clear evaluation set so semantic upgrades are measured by real user utterances instead of intuition.

### 6. Concurrency and Thread-Pool Style Execution

- Improve execution throughput for non-blocking tasks such as memory writes, vector persistence, context enrichment, and provider sync work.
- Move more non-critical side effects off the main response path while keeping consistency-sensitive operations synchronous.
- Introduce safer worker orchestration and bounded concurrency so background tasks scale without creating hidden failure modes.
- Make latency visible through telemetry, tracing, and structured timing logs.

## Longer Term

### 7. Login, Transactions, and Account-Linked Operations

- Add stronger support for authenticated workflows that interact with accounts, services, and transaction-like operations.
- Separate low-risk information retrieval from high-risk operations that may require stricter approval, stronger audit trails, or additional user verification.
- Treat this area as a high-safety surface: anything involving accounts, purchases, bookings, or irreversible actions needs more than basic chat execution.

### 8. Console Maturity

- Continue improving the console so it becomes a real operational center rather than only a management panel.
- Refine device overview, provider management, mission review, memory inspection, and action explainability.
- Improve information density, cross-platform visibility, and recoverability when something fails.
- Add more tools that help users understand what Wanny knows, what Wanny plans to do, and why it made a suggestion.

## Cross-Cutting Principles

- Safety comes before autonomy.
- Real devices and real-world side effects require explainability and auditability.
- New integrations should fit shared abstractions instead of creating permanent one-off logic.
- User trust depends on reliability, restraint, and clear recovery paths.

