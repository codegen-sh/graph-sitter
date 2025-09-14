# CRITICAL: Coding Guidelines
- NEVER go the "ZERO DISRUPTION" approach, eg.: keeping something that is being replaced with backwards compatibility is NO
- NEVER leave fallbacks
- NEVER create bridges
- NEVER create adaptors
- NEVER create "integrations"
- AVOID to create "Managers"
- NEVER use "extended" or "enhanced" concepts to change the code.
    - Changes ALWAYS must be done in the existing code as a formal change.
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
- When finding issues, NEVER adjust implementation to work it around or allow "a quick fix to be reviewed later", ALWAYS fix the issue before proceeding


