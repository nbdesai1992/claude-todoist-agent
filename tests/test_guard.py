"""Tests for the worker guard hook. Run: python3 -m unittest discover -s tests"""
import json
import os
import subprocess
import sys
import unittest

GUARD = os.path.join(os.path.dirname(__file__), "..", "plugins", "todoist-agent", "scripts", "guard.py")
sys.path.insert(0, os.path.dirname(GUARD))
import guard  # noqa: E402

WORKER = "todoist-agent:worker"


def call(tool, agent=WORKER, **tool_input):
    event = {"tool_name": tool, "tool_input": tool_input}
    if agent:
        event["agent_type"] = agent
    return guard.decide(event)


class OnlyTheWorker(unittest.TestCase):
    def test_main_session_untouched(self):
        self.assertIsNone(call("mcp__todoist__add-comments", agent=None))
        self.assertIsNone(call("Bash", agent=None, command="git push"))

    def test_other_subagents_untouched(self):
        self.assertIsNone(call("mcp__claude_ai_Gmail__send_message", agent="Explore"))


class McpTools(unittest.TestCase):
    def test_todoist_blocked_entirely(self):
        for tool in ("mcp__todoist__find-tasks", "mcp__todoist__add-comments",
                     "mcp__claude_ai_Todoist__update-tasks", "mcp__plugin_todoist_todoist__complete-tasks"):
            self.assertIsNotNone(call(tool), tool)

    def test_reads_allowed(self):
        for tool in ("mcp__claude_ai_Slack__slack_search_public_and_private",
                     "mcp__claude_ai_Slack__slack_read_thread",
                     "mcp__claude_ai_Granola__get_meeting_transcript",
                     "mcp__claude_ai_Granola__query_granola_meetings",
                     "mcp__claude_ai_Google_Drive__read_file_content",
                     "mcp__claude_ai_Gmail__search_threads",
                     "mcp__claude_ai_Salesforce_Production__soqlQuery",
                     "mcp__claude_ai_Google_Calendar__list_events",
                     "mcp__claude_ai_Google_Calendar__suggest_time",
                     "mcp__claude_ai_Google_Drive__download_file_content",
                     "mcp__claude_ai_Gmail__get_thread"):
            self.assertIsNone(call(tool), tool)

    def test_outbound_and_destructive_blocked(self):
        for tool in ("mcp__claude_ai_Slack__slack_send_message",
                     "mcp__claude_ai_Slack__slack_send_message_draft",
                     "mcp__claude_ai_Slack__slack_schedule_message",
                     "mcp__claude_ai_Gmail__send_message",
                     "mcp__claude_ai_Gmail__reply",
                     "mcp__claude_ai_Gmail__forward",
                     "mcp__claude_ai_Gmail__trash_thread",
                     "mcp__claude_ai_Gmail__delete_draft",
                     "mcp__claude_ai_Google_Drive__share_file",
                     "mcp__claude_ai_Google_Calendar__respond_to_event",
                     "mcp__claude_ai_Salesforce_Production__deleteSobjectRecord"):
            self.assertIsNotNone(call(tool), tool)

    def test_writes_and_drafts_blocked(self):
        for tool in ("mcp__claude_ai_Google_Calendar__create_event",
                     "mcp__claude_ai_Google_Drive__update_file",
                     "mcp__claude_ai_Google_Drive__create_file",
                     "mcp__claude_ai_Salesforce_Production__updateSobjectRecord",
                     "mcp__claude_ai_Salesforce_Production_-_Sales_Writes__ContactWriteService",
                     "mcp__claude_ai_Gmail__label_thread",
                     "mcp__claude_ai_Gmail__create_draft",
                     "mcp__claude_ai_Gmail__update_draft",
                     "mcp__claude_ai_Slack__slack_create_canvas"):
            self.assertIsNotNone(call(tool), tool)

    def test_unrecognized_tools_blocked(self):
        # Not clearly a read, so not allowed: fail closed on names we can't classify.
        for tool in ("mcp__ide__executeCode", "mcp__some_server__do_thing", "mcp__x__sync"):
            self.assertIsNotNone(call(tool), tool)

    def test_allow_list_opens_writes_but_not_hard_verbs(self):
        original = guard.allow_list
        guard.allow_list = lambda: ["mcp__claude_ai_Gmail__create_draft",
                                    "mcp__claude_ai_Google_Drive__create_file", "mcp__claude_ai_Notion__*"]
        try:
            self.assertIsNone(call("mcp__claude_ai_Gmail__create_draft"))
            self.assertIsNone(call("mcp__claude_ai_Google_Drive__create_file"))
            self.assertIsNone(call("mcp__claude_ai_Notion__update_page"))
            self.assertIsNotNone(call("mcp__claude_ai_Notion__delete_page"))
            self.assertIsNotNone(call("mcp__claude_ai_Google_Drive__copy_file"))
        finally:
            guard.allow_list = original


class Builtins(unittest.TestCase):
    def test_builtin_outbound_blocked(self):
        for tool in ("SendMessage", "CronCreate", "RemoteTrigger", "PushNotification"):
            self.assertIsNotNone(call(tool), tool)

    def test_local_tools_allowed(self):
        for tool in ("Read", "Grep", "Glob", "WebSearch", "WebFetch"):
            self.assertIsNone(call(tool), tool)

    def test_settings_protected(self):
        self.assertIsNotNone(call("Write", file_path="~/.claude/settings.json"))
        self.assertIsNotNone(call("Edit", file_path=os.path.expanduser("~/.config/todoist-agent/config.toml")))
        self.assertIsNone(call("Write", file_path=os.path.expanduser("~/todoist-agent/1-x/notes.md")))


class Bash(unittest.TestCase):
    def test_blocked(self):
        for cmd in ("git push origin claude/1-x",
                    "cd /repo && git push",
                    "git reset --hard HEAD~1",
                    "git clean -fd",
                    "git checkout -- src/app.py",
                    "git checkout .",
                    "git restore src/app.py",
                    "git stash drop",
                    "git branch -D old",
                    "gh pr create --fill",
                    "gh issue comment 12 --body hi",
                    "gh api repos/o/r/issues -X POST",
                    "gh api repos/o/r/issues -f title=x",
                    "npm publish",
                    "curl -X POST https://hooks.slack.com/x",
                    "curl -d '{}' https://api.example.com",
                    "sudo rm -rf /tmp/x",
                    "ssh host ls",
                    "osascript -e 'tell app \"Mail\" to send'",
                    "rm -rf ~",
                    "rm -rf /",
                    "rm -rf .."):
            self.assertIsNotNone(call("Bash", command=cmd), cmd)

    def test_allowed(self):
        for cmd in ("git status",
                    "git -C /repo worktree add /out/worktree -b claude/1-x",
                    "git add -A && git commit -m 'fix'",
                    "git checkout -b claude/1-x",
                    "git log --oneline",
                    "gh pr view 12",
                    "gh pr list",
                    "gh api repos/o/r/pulls",
                    "curl -s https://example.com",
                    "rm -rf ./build",
                    "cat draft-mail.md",
                    "grep -r email src/",
                    "python3 -m pytest",
                    "mkdir -p ~/todoist-agent/1-x"):
            self.assertIsNone(call("Bash", command=cmd), cmd)


class HookProtocol(unittest.TestCase):
    def run_hook(self, event):
        out = subprocess.run([sys.executable, GUARD], input=json.dumps(event),
                             capture_output=True, text=True, check=True).stdout
        return json.loads(out) if out.strip() else None

    def test_deny_json(self):
        out = self.run_hook({"agent_type": WORKER, "tool_name": "mcp__todoist__delete-object", "tool_input": {}})
        spec = out["hookSpecificOutput"]
        self.assertEqual(spec["hookEventName"], "PreToolUse")
        self.assertEqual(spec["permissionDecision"], "deny")

    def test_silent_when_allowed_or_not_worker(self):
        self.assertIsNone(self.run_hook({"agent_type": WORKER, "tool_name": "Read", "tool_input": {}}))
        self.assertIsNone(self.run_hook({"tool_name": "mcp__todoist__delete-object", "tool_input": {}}))

    def test_bad_input_is_silent(self):
        out = subprocess.run([sys.executable, GUARD], input="not json", capture_output=True, text=True)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout, "")


if __name__ == "__main__":
    unittest.main()
