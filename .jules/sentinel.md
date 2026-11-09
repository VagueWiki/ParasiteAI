## 2024-05-18 - PowerShell Backtick Obfuscation Evasion
**Vulnerability:** PowerShell aliases (`iwr`, `irm`) could be evaded in CLIExecutionSandbox security regexes via backtick insertion (e.g., `i`wr`).
**Learning:** Shell-specific character escapes (like PowerShell's backtick) bypass static regex lists designed for plain string detection.
**Prevention:** Sanitize the command string by stripping the escape character (`` ` ``) purely for the purpose of regex matching, avoiding modification of the string passed to Popen.
