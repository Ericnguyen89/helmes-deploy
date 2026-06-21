---
name: sysadmin
description: Server administration and infrastructure tasks
tools: bash, file_read, file_write
---

## System Administration Skill

You are performing server administration. Follow this workflow:

1. **Assess**: Check the current state before making changes (status, logs, config).
2. **Plan**: State what you will change and potential risks.
3. **Execute**: Make changes carefully. Use `&&` to chain related commands.
4. **Verify**: Confirm the change took effect (check status, test connectivity).

### Efficiency Rules
- Chain related commands with `&&` instead of separate tool calls
- Check status AND logs in the same bash call when possible
- Always verify changes immediately after applying them
- For config changes: backup → edit → test → reload, all in one flow
