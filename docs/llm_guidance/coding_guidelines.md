# CRITICAL: Coding Guidelines
- NEVER go the "ZERO DISRUPTION" approach, eg.: keeping something that is being replaced with backwards compatibility is NO
- NEVER leave fallbacks
- NEVER create bridges
- NEVER create adaptors
- NEVER create "integrations"
- AVOID to create "Managers"
- NEVER create what-so-ever-workaround-to-glue-legacy-code
- ALWAYS use clever architecture
- ALWAYS think and implement form broader architecture and creating a data flow and schema and then implement the details
- NEVER leave tests suites or validation code behind, unless 🧠 is explicit about it
- MUST keep files organized and code lean - no bloating with peripherals
- The following things are FORBIDDEN to be added to the code without permission:
    - caching
    - router
    - performance checks
    - monitoring (unless for debugging)
    - Manager
    - orchestrator
    - validator (integration validator)


