"""Tests for the worker guard hook. Run: python3 -m unittest discover -s tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

GUARD = os.path.join(os.path.dirname(__file__), "..", "plugins", "relay", "scripts", "guard.py")
sys.path.insert(0, os.path.dirname(GUARD))
import guard  # noqa: E402

WORKER = "relay:worker"


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

    def test_worker_id_is_relay(self):
        self.assertEqual(guard.WORKER, "relay:worker")
        self.assertIsNotNone(call("Bash", agent="relay:worker", command="git push"))
        # The pre-0.5 id no longer exists, so it's just another subagent.
        self.assertIsNone(call("Bash", agent="todoist-agent:worker", command="git push"))


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
        self.assertIsNone(call("Write", file_path=os.path.expanduser("~/relay/1-x/notes.md")))

    def test_both_config_dirs_protected(self):
        for path in ("~/.config/relay/config.toml", "~/.config/todoist-agent/config.toml"):
            self.assertIsNotNone(call("Edit", file_path=os.path.expanduser(path)), path)
            self.assertIsNotNone(call("Write", file_path=path), path)


class ConfigPath(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.new = os.path.join(self.tmp.name, "relay", "config.toml")
        self.old = os.path.join(self.tmp.name, "todoist-agent", "config.toml")
        self.saved = guard.CONFIG, guard.LEGACY_CONFIG
        guard.CONFIG, guard.LEGACY_CONFIG = self.new, self.old

    def tearDown(self):
        guard.CONFIG, guard.LEGACY_CONFIG = self.saved
        self.tmp.cleanup()

    def write(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write('[worker]\nallow_tools = ["mcp__x__create_thing"]\n')

    def test_default_paths(self):
        self.assertEqual(self.saved[0], os.path.expanduser("~/.config/relay/config.toml"))
        self.assertEqual(self.saved[1], os.path.expanduser("~/.config/todoist-agent/config.toml"))

    def test_falls_back_to_old_path_when_only_it_exists(self):
        self.write(self.old)
        self.assertEqual(guard.config_path(), self.old)

    def test_new_path_wins_when_both_exist(self):
        self.write(self.old)
        self.write(self.new)
        self.assertEqual(guard.config_path(), self.new)

    def test_new_path_when_neither_exists(self):
        self.assertEqual(guard.config_path(), self.new)

    @unittest.skipIf(sys.version_info < (3, 11), "allow_tools needs tomllib (Python 3.11+)")
    def test_allow_list_read_from_old_path(self):
        self.write(self.old)
        self.assertEqual(guard.allow_list(), ["mcp__x__create_thing"])


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
                    "mkdir -p ~/relay/1-x"):
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
