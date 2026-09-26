# claude-todoist-agent

**Hand tasks to Claude in Todoist. Claude does them in the right project folder. You review what comes back.**

## What this is

A **Claude Code plugin**: a small bundle of instructions and a safety check that you install into Claude Code. That's all. There's no server, no API key, and nothing to host.

It connects two things you already have:

| You bring | What it's for |
|---|---|
| **Todoist** (your account) | Where you hand off tasks and read results. Claude reaches it through Todoist's official MCP connector. |
| **Claude Code** (your Claude subscription: Pro, Max, Team, or Enterprise) | Does the work, on your computer, under your login. Runs use your plan's normal usage. |

**What the plugin adds:**

| Piece | What it does |
|---|---|
| `/todoist-agent:setup` | One-time setup: labels, config, approval rules. |
| `/todoist-agent:delegate` | Turns a request into a clear Todoist task for Claude. |
| `/todoist-agent:run` | Works every task labeled `@claude` and posts the results back. |
| `/todoist-agent:review` | Walks you through what came back. |
| Worker agent | Does a single task. It can read your connected tools (Slack, Drive, email, meeting notes…) and write files in the project folder, but can't touch Todoist. |
| Guard | A safety check that stops the worker from sending, sharing, deleting, completing, or pushing anything. |

Nothing runs in the background. Work only happens when you type `/todoist-agent:run`.

## Setup (once, about 10 minutes)

**1. Install Claude Code and sign in** with your Claude account: see [code.claude.com](https://code.claude.com). Run `claude` in a terminal and follow the login. You also need `python3` (for the safety check; macOS and most Linux have it) and `git` (for code tasks).

**2. Connect Todoist.** In a terminal:

```bash
claude mcp add --transport http --scope user todoist https://ai.todoist.net/mcp
```

Then start `claude`, type `/mcp`, pick **todoist**, choose **Authenticate**, and approve in the browser. (If you've already added Todoist as a connector on claude.ai, that works too. Skip this step.)

**3. Install the plugin.** Inside Claude Code:

```
/plugin marketplace add nbdesai1992/claude-todoist-agent
/plugin install todoist-agent@claude-todoist-agent
```

Restart Claude Code (`/exit`, then `claude`).

**4. Run setup.** Inside Claude Code:

```
/todoist-agent:setup
```

It checks Todoist, then asks two things:
- **Your label:** the label for tasks on your turn. Your first name works, e.g. `@sam`.
- **Your projects folder:** the folder that holds one subfolder per project, e.g. `~/Projects`. Claude puts each task's files in the right subfolder.

Then it creates the labels `@claude`, `@claude-working`, and yours in Todoist, and writes `~/.config/todoist-agent/config.toml`. It also offers approval prompts for risky Todoist actions (delete, complete), so those always ask you first.

**5. (Optional) Teach Claude your projects.** Add a `CLAUDE.md` to any project folder saying how work there should be done: sources to check, house style, where drafts go. Connect other tools in Claude Code (Slack, Google Drive, Gmail, meeting notes) and the workers can read them for context.

**6. Try it:**

```
/todoist-agent:delegate Find 3 highly rated standing desks under $500. Done when there's a comparison table with prices and links.
/todoist-agent:run
```

Then open the task in Todoist and read Claude's comment.

**Updating:** in a terminal, `claude plugin marketplace update claude-todoist-agent && claude plugin update todoist-agent@claude-todoist-agent`, then restart Claude Code.

## Daily use (your part)

You only ever do three things. A label on each task shows whose turn it is.

### 1. Hand it off → `@claude`

Pick either way:
- **In Todoist** (phone, desktop, anywhere): add the `@claude` label to a task.
- **In Claude Code:** `/todoist-agent:delegate <what you want>`. Claude writes a clear brief (goal, what "done" looks like, which project folder) and asks you if anything's unclear.

The more specific the task, the better the first result. Say which project it belongs to, or Claude will ask.

### 2. Run the queue → `/todoist-agent:run`

Open Claude Code **in your projects folder** and type `/todoist-agent:run`. Then walk away.

- Claude works every `@claude` task at the same time, each in its own project folder.
- Files land in that project folder. Code lands on a `claude/…` branch, never on your working copy.
- When it's done, each task has a comment with the result, and its label is back to **you**.

### 3. Review → your label

Open the task in Todoist (or run `/todoist-agent:review`). The comment starts with one of:

| | Meaning | What you do |
|---|---|---|
| ✅ | Ready for review | Check the files it links to. |
| 🟡 | Partly done | See what's left under "Your next steps". |
| ❓ | Needs your input | Answer its questions (often: which folder?). |

Then pick one:
- **Send it back:** reply in a comment, then switch the label to `@claude`. The next run picks it up and builds on the same files.
- **Keep it:** do nothing. It's on your plate now.
- **Done:** complete the task, in Todoist or by choosing "Complete it" in `/todoist-agent:review`. Claude never completes a task on its own.

```
   you: label @claude  ──►  you: /todoist-agent:run  ──►  you: review the comment
        (or /delegate)        Claude works, in the        ✅ 🟡 ❓
                              project folder              │
                                                          ├─ send back → @claude (loop)
                                                          ├─ keep it
                                                          └─ complete it
```

**What Claude will never do:** send, post, share, delete, complete, or push anything. It reads your Slack, meeting notes, docs, email, and the web, and leaves you files, drafts, and branches to act on. A guard enforces this, even in bypass mode.

## Commands

| | |
|---|---|
| **Delegate** | `/todoist-agent:delegate <what>` writes a task in the template and labels it `@claude`. Or add `@claude` to any task yourself, from your phone or anywhere. Other agents can delegate too: see [docs/delegation-template.md](docs/delegation-template.md). |
| **Run** | `/todoist-agent:run` works the whole queue. Use `/todoist-agent:run <task>` for one task, or `--dry-run` to see the plan without running anything. The run claims each task (`@claude` → `@claude-working`) before starting it, so a second run skips it. If a run dies, the next run lists the leftover `@claude-working` tasks and offers to requeue them. |
| **Review** | `/todoist-agent:review` goes through what came back. Or review in the Todoist app: reply in a comment and switch the label back to `@claude` to send a task back. |

### The delegation template

```
**Goal:** Compare standing desks under $500 for a small home office.
**Done when:** A markdown table of the top 3 with prices, links, and a recommendation.
**Folder:** /Users/me/projects/home-office   (or just home-office, under a root)
**Context:** Needs a crossbar. See the #home-office Slack thread from last week.
**Stop before:** Don't buy anything.     (optional)
**Model:** sonnet                        (optional; default Opus, high effort)
```

The delegate skill always fills it in, including the folder: it matches the task to an existing project folder or proposes a new one. Tasks you write by hand don't have to follow it. A worker scopes whatever it gets, and if the task isn't clear enough it hands the task back with specific questions.

### Models

Workers run in your Claude Code session, on your account. By default they use **Opus at high effort** (set in `agents/worker.md`). To change the model for every task, set `run.model`. For a single task, add a `**Model:**` line. Effort can only be set in the worker definition, because Claude Code's subagent call accepts a model but not an effort level.

### Connectors

Workers get the same MCP connectors as the session you run from (claude.ai connectors, `claude mcp add` servers). Whatever is connected and signed in there, they can read. Nothing to configure per worker.

### Folders

Claude Code can't start a subagent in a different working directory. So the dispatcher works out each task's folders and passes them in as absolute paths. The worker uses them in every command and reads the work folder's `CLAUDE.md` itself.

Every task runs in a **work folder**, and its files land there, next to the rest of that project. The folder comes from:

1. the task's `Folder:` line: an absolute path, or a bare name like `home-office` that means that subfolder of one of your `folders.roots`;
2. otherwise the Todoist project's folder in `folders.projects`;
3. otherwise nothing: the run hands the task back ❓ with the 2–3 best-fitting project folders as options. It doesn't guess.

A `Folder:` that doesn't exist yet but sits directly inside a root is a new project, and the run creates it. **Put a `CLAUDE.md` in a project folder to tell workers how tasks there should be done**: which sources to check, the house style, where outputs go, how to run tests.

If the work folder is a git repository, the worker leaves your checkout alone. It creates a worktree at `~/todoist-agent/<task-id>-<slug>/worktree` on a `claude/<task-id>-<slug>` branch, commits there, and never pushes. That's the only thing `folders.workspace` is for.

## Safety

- **Workers:** a PreToolUse hook (`plugins/todoist-agent/scripts/guard.py`) acts only on calls from the worker subagent. Outside systems are read-only:
  - **MCP tools run only if they're clearly reads** (get, list, search, read, query…). Anything else is denied, including drafts and tool names it can't classify.
  - **Send, share, post, schedule, delete, trash, archive, and complete** stay denied on every server, even for tools you allow.
  - **Every Todoist tool** is denied, since the dispatcher owns Todoist.
  - **Shell commands** that push (`git push`), discard work (destructive git), write through `gh` or `curl`, publish packages, or use `ssh` or `sudo` are denied.
  - **Settings:** edits to `~/.claude/` and the todoist-agent config are denied.

  Hook denials apply even in bypass-permissions mode. The worker's `disallowedTools` also removes Todoist and messaging tools up front.
- **The run step** only swaps labels and posts one comment per task.
- **Review** completes a task only when you pick "Complete it".
- **Your approval rules:** setup recommends `ask` rules for the Todoist tools that delete, complete, or reach other people. Claude Code honors explicit `ask` rules in every permission mode.

### Permissions

Workers run in your Claude Code session and inherit its working directory and permission mode. **Start runs from your root folder** (the parent of your project folders), so every work folder is inside the session. In the default mode, workers will still stop to ask about shell commands and edits. For unattended runs, use `claude --permission-mode acceptEdits` or `bypassPermissions`: the guard hook above and your `ask` rules still apply in both.

## Configuration

`~/.config/todoist-agent/config.toml`. Every key is optional.

```toml
[labels]
claude = "claude"            # Claude's turn
human = "human"              # your turn, e.g. your first name
working = "claude-working"   # claimed by a run, in progress

[folders]
roots = []                              # folders whose subfolders are projects, e.g. ["~/Projects"]
workspace = "~/todoist-agent"          # git worktrees live here

[folders.projects]                      # Todoist project → work folder (overrides roots)
# "Side project" = "~/code/side-project"

[run]
max_parallel = 4                        # workers started at once
model = ""                              # worker model for every task: opus, sonnet, haiku, fable
                                        # empty = worker default (Opus, high effort)

[context]
about = ""        # who you are, your role, house style; given to every worker
sources = ""      # where context lives, e.g. "work threads in Slack, meeting notes in Granola"

[worker]
allow_tools = []  # exceptions to read-only, e.g. ["mcp__claude_ai_Gmail__create_draft"]
                  # send/share/delete-style tools stay blocked regardless. Needs Python 3.11+.
```

## Layout

```
plugins/todoist-agent/
  skills/delegate  run  review  setup    the workflow, as Claude Code skills
  agents/worker.md                       the worker subagent: scope, do, report
  hooks/hooks.json, scripts/guard.py     worker guardrails
docs/delegation-template.md              instructions to paste into other agents
tests/test_guard.py                      python3 -m unittest discover -s tests
```

## Roadmap

- **Scheduled runs:** the run step is a plain skill, so a schedule is `claude -p "/todoist-agent:run"` on cron or launchd. That comes after manual runs have proven themselves.

## License

MIT
