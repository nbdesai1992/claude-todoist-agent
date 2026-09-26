---
name: run
description: Work the Claude queue in Todoist. Finds every task labeled for Claude, starts one worker subagent per task in the right folder, posts each result as a comment on its task, and hands the task back to the human for review. Use when the user says to run the queue, "run the Claude tasks", "work my Todoist queue", or "do the delegated tasks".
argument-hint: "[--dry-run] [task name or ID to run just that one]"
---

# Run the Claude queue

You are the dispatcher. You read Todoist, start workers, and write the results back. The workers do the actual tasks. They never touch Todoist.

The only Todoist writes you make here are **label swaps** and **one comment per task**:

- **Claim:** Claude label → working label, before any work starts. Other runs only pick up the Claude label, so a claimed task can't be run twice.
- **Result:** post the comment, then swap the working label → the human label.

Never complete, delete, reschedule, move, or edit the title or description of a task.

## 1. Settings

Read `~/.config/relay/config.toml` if it exists (if only the old `~/.config/todoist-agent/config.toml` exists, read that instead). Defaults for anything missing:

| Key | Default |
|---|---|
| `labels.claude` | `claude` |
| `labels.human` | `human` |
| `labels.working` | `claude-working` |
| `folders.roots` | none (folders whose subfolders are projects, e.g. `~/Projects`) |
| `folders.projects` | none (Todoist project name → work folder) |
| `folders.workspace` | `~/relay` (git worktrees only) |
| `run.max_parallel` | `4` |
| `run.model` | none (the worker's default: Opus, high effort) |
| `context.about`, `context.sources` | empty |

Expand `~` to the real home directory in every path you pass on.

## 2. Collect and claim

1. **Leftovers:** `find-tasks` with `labels: [<working label>]`. These are claimed but unfinished. Either another run is working on them right now, or an earlier run died. List them and ask the user (AskUserQuestion) whether to put them back in the queue: swap the working label → the Claude label, then include them below. Default to leaving them alone. In a dry run, just list them.
2. **Queue:** `find-tasks` with `labels: [<claude label>]` and `limit: 100`. If `$ARGUMENTS` names a task (an ID, a link, or words from the title), keep only that one. If the queue is empty, say so in one line and stop.
3. **Claim right away,** before anything else: one `update-tasks` call (up to 25 tasks per call), setting each task's `labels` to its current labels minus the Claude label, plus the working label. `labels` replaces the whole list, so keep the others. Send only `id` and `labels`. Skip this step in a dry run.
4. `find-projects` once, to map project IDs to names.
5. For each task, `find-comments` with its `taskId`. Follow the `cursor` until you have them all. Earlier Claude results and the human's replies are how feedback reaches the worker.

## 3. Prepare each task

For each task work out:

- **Slug:** the task ID, then a dash, then 3–5 lowercase words from the title joined by hyphens (e.g. `8123-research-standing-desks`).
- **Work folder:** where the task happens and where its files go. In order:
  1. The `**Folder:**` line in the description. An absolute path (or `~/…`) is used as is. A bare name (`home-office`) means that subfolder of one of `folders.roots`.
  2. The task's Todoist project in `folders.projects`.
  3. Neither: hand it back (below). Don't guess.

  If the folder doesn't exist but sits directly inside one of `folders.roots`, it's a new project: create it with `mkdir -p`. Otherwise hand it back.
- **Git:** if the work folder is inside a git repo (`git -C <folder> rev-parse --show-toplevel`), the worker works in a worktree at `<workspace>/<slug>/worktree` on branch `claude/<slug>`, so the owner's checkout stays untouched. Don't create it; the worker does.
- **Hand straight back** without starting a worker if:
  - there's no work folder. List the subfolders of `folders.roots` and offer the 2–3 that best fit the title and description, plus a new `<root>/<kebab-name>`, as options: *Add a **Folder:** line (or reply with one) and switch the label back to @<claude label>.*
  - the work folder doesn't exist and can't be created (see above), or
  - the task also has the human label (it's unclear whose turn it is).

  In each case post a comment explaining the problem (format in step 5, status ❓) and swap the working label → the human label.

Everything else goes to a worker. The worker decides whether the task is clear enough to do. Tasks written by the human don't need to follow the delegation template.

**Dry run** (`--dry-run` in `$ARGUMENTS`): show a table of task → work folder (mark new ones "new", git ones "worktree") → model → "run" or "hand back: <reason>", then stop. Don't claim, create folders, or write to Todoist.

## 4. Start the workers

Before starting, show one line per task: title → work folder → model.

**Permissions:** workers inherit this session's working directory and permission mode. If a work folder is outside the current working directory, say so once: workers may stop on permission prompts, and a headless run fails. The fix is to start the run from the root folder (the parent of the project folders).

Start one **`relay:worker`** subagent per task with the Agent tool. Put up to `run.max_parallel` Agent calls in a single message so they run in parallel, then do the next batch.

- **Model:** if the description has a `**Model:**` line (`opus`, `sonnet`, `haiku`, or `fable`), pass it as the Agent `model`. Otherwise pass `run.model` if it's set. Otherwise leave `model` out, and the worker's default applies (Opus at high effort). Effort can't be set per task.
- **Description:** `Todoist: <short title>`.
- **Prompt:** the task packet:

```
TASK PACKET
Task ID: <id>
Title: <content>
Link: <url>
Project: <project name>
Priority: <p1–p4>   Due: <due date or none>
Run date: <today>
Work folder: <absolute path>
Git worktree (only if the work folder is in a git repo): <workspace>/<slug>/worktree on branch claude/<slug>

Description:
<the full description, verbatim>

Comment history, oldest first (earlier results from Claude and replies from the human):
<author or "Claude"/"human" · date · text, or "none">

About the owner: <context.about or "not provided">
Where to look for context: <context.sources or "use the tools you have">
```

## 5. Write the results back

Each worker ends its reply with a `RESULT` block (STATUS, SCOPE, SUMMARY, ARTIFACTS, NEXT STEPS, QUESTIONS). For each task, in this order:

1. **Comment:** Todoist `add-comments` with `taskId`, `notifyUsers: ["none"]`, and this content:

   ```
   🤖 Claude · <✅ Ready for review | 🟡 Partly done | ❓ Needs your input>
   *Scope:* <SCOPE>

   <SUMMARY>

   **Artifacts**
   - <each ARTIFACTS line>

   **Your next steps**
   - <each NEXT STEPS line>

   **Questions**
   - <each QUESTIONS line>

   *<run date> · folder: <work folder, or the worktree for git>*
   ```

   Map STATUS `done` → ✅, `partial` → 🟡, `needs-input` → ❓. Leave out any section that's empty. For 🟡 and ❓, end with: *Reply in a comment, then switch the label back to @<claude label> to send it back.*

2. **Label swap:** `update-tasks` with `labels` = the task's current labels, minus the working label, plus the human label (send only `id` and `labels`).

If the comment fails, swap the working label back → the Claude label so the task is queued again, and report the error.

If a worker returns no RESULT block, crashes, or runs out of time, post a ❓ comment saying the run failed (with anything useful it returned) and swap to the human label anyway, so nothing stays claimed.

## 6. Report

Finish with a short table: task · status (✅/🟡/❓) · one-line result · folder. Then one line: "Run `/relay:review` to go through them."
