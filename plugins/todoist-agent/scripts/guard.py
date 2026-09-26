"""PreToolUse guard for the todoist-agent worker subagent.

Claude Code tags tool calls made inside a subagent with `agent_type`. This hook only acts on
calls from `todoist-agent:worker`; every other session and subagent passes through untouched.

For the worker, outside systems are read-only:
  * every Todoist tool is denied (the dispatcher owns Todoist),
  * an MCP tool is allowed only if its name is clearly a read (get, list, search, read...),
  * send/share/delete-style tools are denied even if allow-listed,
  * other writes (create, update, drafts...) are denied unless the user allows the tool in
    ~/.config/todoist-agent/config.toml under [worker] allow_tools,
  * shell commands that push, publish, send, or discard work are denied,
  * edits to Claude Code and todoist-agent settings are denied.

Deny decisions apply even in bypassPermissions mode. Runs on the system python3 (3.8+).
"""
from __future__ import annotations

import json
import os
import re
import sys

WORKER = "todoist-agent:worker"
CONFIG = os.path.expanduser("~/.config/todoist-agent/config.toml")

# Never allowed, even for allow-listed tools.
HARD_VERBS = {
    "send", "forward", "reply", "respond", "post", "publish", "share", "invite", "schedule",
    "delete", "trash", "remove", "archive", "complete", "spam", "assign", "merge", "approve",
    "sign", "pay", "transfer", "purchase", "submit", "notify", "unsubscribe", "revoke",
}
# Read-only tool names. An MCP tool must contain one of these (and no write verb) to run.
READ_VERBS = {
    "get", "list", "search", "read", "find", "fetch", "query", "view", "download", "describe",
    "lookup", "retrieve", "count", "suggest", "info",
}
# Allowed only for allow-listed tools.
WRITE_VERBS = {
    "create", "update", "add", "set", "write", "edit", "modify", "patch", "upload", "insert",
    "move", "copy", "rename", "label", "unlabel", "import", "apply", "mark", "untrash",
    "uncomplete", "reschedule", "reorder", "restore", "manage", "put",
}
BUILTIN_DENY = {"SendMessage", "CronCreate", "CronDelete", "RemoteTrigger", "PushNotification",
                "ScheduleWakeup"}

BASH_DENY = [
    (r"\bgit\s+push\b", "git push"),
    (r"\bgit\s+reset\s+.*--hard\b", "git reset --hard"),
    (r"\bgit\s+clean\b", "git clean"),
    (r"\bgit\s+checkout\s+(.*\s)?--(\s|$)|\bgit\s+checkout\s+\.(\s|$)", "git checkout that discards changes"),
    (r"\bgit\s+restore\b", "git restore"),
    (r"\bgit\s+stash\s+(drop|clear)\b", "git stash drop/clear"),
    (r"\bgit\s+branch\s+(.*\s)?-D\b", "git branch -D"),
    (r"\bgh\s+api\b.*(\s-X\s*|\s--method\s+)(POST|PUT|PATCH|DELETE)", "gh api write"),
    (r"\bgh\s+api\b.*\s(-f|-F|--field|--raw-field|--input)\s", "gh api write"),
    (r"\bgh\s+(pr|issue)\s+(create|merge|close|reopen|comment|review|edit|delete|lock|ready)\b", "gh write"),
    (r"\bgh\s+(release|repo|gist|secret|variable|workflow|label)\s+(create|delete|edit|upload|set|run|enable|disable|fork|rename|archive)\b", "gh write"),
    (r"\b(npm|pnpm|yarn)\s+publish\b|\btwine\s+upload\b|\bcargo\s+publish\b|\bgem\s+push\b|\bdocker\s+push\b", "publishing a package"),
    (r"\bcurl\b.*(\s-X\s*|\s--request\s+)(POST|PUT|PATCH|DELETE)\b", "curl write request"),
    (r"\bcurl\b.*\s(-d|--data\S*|-F|--form|-T|--upload-file)(\s|=)", "curl upload"),
    (r"\bwget\b.*--(post|method)", "wget write request"),
    (r"(^|[;&|(]\s*)(sudo|ssh|scp|osascript|sendmail|mail)(\s|$)", "a command that reaches outside the task"),
    (r"\brm\s+(-\S*\s+)*(/|~|~/|\$HOME|\$HOME/|\.\.|\.\./?)(\s|$)", "rm of a top-level folder"),
]

PROTECTED_PATHS = [os.path.expanduser("~/.claude/"), os.path.expanduser("~/.config/todoist-agent/")]


def words(name: str) -> set[str]:
    """Split a tool name like 'slack_send_message' or 'createSobjectRecord' into lowercase words."""
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    return {w.lower() for w in re.split(r"[^A-Za-z0-9]+", name) if w}


def allow_list() -> list[str]:
    try:
        import tomllib  # Python 3.11+
        with open(CONFIG, "rb") as f:
            return list(tomllib.load(f).get("worker", {}).get("allow_tools", []))
    except Exception:
        return []


def allowed_by_config(tool: str) -> bool:
    for pattern in allow_list():
        if pattern == tool or (pattern.endswith("*") and tool.startswith(pattern[:-1])):
            return True
    return False


def check_mcp(tool: str) -> str | None:
    parts = tool.split("__", 2)
    if len(parts) < 3:
        return None
    server, name = parts[1], parts[2]
    if "todoist" in server.lower():
        return "The worker doesn't touch Todoist; the dispatcher posts your result."
    w = words(name)
    hard = w & HARD_VERBS
    if hard:
        return f"'{name}' would {sorted(hard)[0]} something. Write it as a file and list it under NEXT STEPS."
    if allowed_by_config(tool):
        return None
    if w & WRITE_VERBS or not w & READ_VERBS:
        return (f"'{name}' isn't read-only. Outside systems are read-only for the worker: put the "
                "result in a local file instead (the owner can allow this tool under "
                "[worker] allow_tools).")
    return None


def check_bash(command: str) -> str | None:
    for pattern, label in BASH_DENY:
        if re.search(pattern, command):
            return f"Blocked {label}. Do the local part and list the rest under NEXT STEPS."
    return None


def check_path(path: str) -> str | None:
    full = os.path.abspath(os.path.expanduser(path))
    for protected in PROTECTED_PATHS:
        if full.startswith(protected):
            return "The worker can't change Claude Code or todoist-agent settings."
    return None


def decide(event: dict) -> str | None:
    """Return a deny reason, or None to leave the call to normal permissions."""
    if event.get("agent_type") != WORKER:
        return None
    tool = event.get("tool_name", "")
    args = event.get("tool_input") or {}
    if tool in BUILTIN_DENY:
        return f"The worker can't use {tool}."
    if tool.startswith("mcp__"):
        return check_mcp(tool)
    if tool == "Bash":
        return check_bash(args.get("command", ""))
    if tool in ("Write", "Edit", "NotebookEdit"):
        return check_path(args.get("file_path") or args.get("notebook_path") or "")
    return None


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return
    reason = decide(event)
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "todoist-agent guard: " + reason,
        }}))


if __name__ == "__main__":
    main()
