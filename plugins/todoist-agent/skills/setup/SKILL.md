---
name: setup
description: One-time setup for Relay (the Todoist agent). Checks the Todoist connection, creates the two turn labels, writes the config file, and checks the approval rules. Use when the user wants to set up or repair Relay (the Todoist agent), or when another todoist-agent skill reports it isn't set up.
disable-model-invocation: true
---

# Set up Relay

Do each step, say what you found in a line, and fix what's missing. Ask before changing anything the user already has.

1. **Todoist connection.** Call the Todoist `user-info` tool. If there's no Todoist MCP server, tell the user to add one and stop:
   `claude mcp add --transport http --scope user todoist https://ai.todoist.net/mcp`, then `/mcp` → todoist → Authenticate. A claude.ai Todoist connector works too.

2. **Config.** If `~/.config/todoist-agent/config.toml` doesn't exist, ask the user what their turn label should be (suggest their first name in lowercase, or `human`). Then write the file from the example in this plugin's README ("Configuration"), filling in that label. Also ask where their projects live (a folder whose subfolders are projects, e.g. `~/Projects`) and set `folders.roots`. Leave the other keys at their defaults and offer to fill in `context.about` and `context.sources`.

3. **Labels.** `find-labels` for the Claude, working, and human labels from the config. Create any that are missing with `add-labels` (Claude: `violet`, working: `lavender`, human: `orange`).

4. **Workspace.** `mkdir -p` the `folders.workspace` directory (default `~/todoist-agent`; it holds git worktrees). Tell the user to start `/todoist-agent:run` from their root folder, so workers can work in every project folder (README, "Permissions").

5. **Approval rules.** Read `~/.claude/settings.json` and look at `permissions.ask`.
   - Recommend `ask` rules for the Todoist tools that remove things or reach other people: `delete-object`, `complete-tasks`, `manage-assignments`, `project-management`, `project-move`, `update-comments`. The rule format is `mcp__<server>__<tool>`, e.g. `mcp__todoist__delete-object`.
   - `/todoist-agent:run` posts results with `add-comments`. If `add-comments` is in `ask`, every result prompts. Tell the user, and offer to remove that one rule.

   Show the exact change and get a yes before editing the file.

6. **Try it.** Suggest: "Run `/todoist-agent:delegate` with something small, then `/todoist-agent:run`."
