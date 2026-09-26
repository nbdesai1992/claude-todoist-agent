---
name: review
description: Review what Claude handed back in Todoist. Goes through each task on the human's turn that has a Claude result, shows the result and its artifacts, then sends it back with feedback, keeps it, or completes it on the user's say-so. Use when the user wants to review Claude's work, check what came back, clear the review queue, or answer Claude's questions.
argument-hint: "[task name or ID to review just that one]"
---

# Review Claude's work

Go through the tasks Claude handed back, one at a time. The user decides what happens to each one. You only carry it out.

## 1. Collect

- Read `~/.config/relay/config.toml` (if only the old `~/.config/todoist-agent/config.toml` exists, read that instead) for `labels.claude` (default `claude`) and `labels.human` (default `human`).
- Todoist `find-tasks` with `labels: [<human label>]` and `limit: 100`. If `$ARGUMENTS` names a task, keep only that one.
- For each task, `find-comments` (follow the `cursor`). The latest comment starting with `🤖 Claude` is the result. Tasks with no Claude comment are the user's own to-dos: skip them and report only how many you skipped.

If nothing is waiting, say so in one line and stop.

## 2. Overview

List the tasks first: status (✅/🟡/❓), title with link, one-line summary. Put ❓ (needs input) first, since those are blocked on the user.

## 3. One task at a time

For each task:

1. Show the result: scope, summary, artifacts, next steps, questions. For artifacts that are local files, read them and show the key part (or all of it if it's short). For a git branch, show `git log --oneline` and `git diff --stat` against the base branch. Offer to show more.
2. Ask with AskUserQuestion what to do:
   - **Send back with feedback:** Claude goes again with the user's notes. If the task has questions, this is how the user answers them.
   - **Keep it, it's mine now:** leave the task as it is (it keeps the human label).
   - **Complete it:** the work is done and nothing else is left on the task.
   - **Skip for now**
3. Do it:
   - **Send back:** get the feedback text (the user's own words from "Other", or ask). Post it with `add-comments` (`notifyUsers: ["none"]`) as `💬 Feedback: <text>`. Then `update-tasks` with `labels` = current labels minus the human label, plus the Claude label (send only `id` and `labels`).
   - **Complete:** only on the user's explicit choice. Call `complete-tasks`. Claude Code may ask the user to confirm, which is expected.
   - **Keep** / **Skip:** no change.

Never delete tasks or comments. Never change a task's title, description, date, or project here.

## 4. Wrap up

One line per task with what happened. If anything was sent back, ask whether to run `/relay:run` now.
