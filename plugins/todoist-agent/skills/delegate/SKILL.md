---
name: delegate
description: Hand a piece of work to Claude through Todoist. Creates (or converts) a Todoist task in the delegation template and labels it for Claude, so the next /todoist-agent:run picks it up. Use when the user says to delegate something, "have Claude do this later", "queue this for Claude", "add this as a task for Claude", or wants an existing Todoist task handed to Claude.
argument-hint: "[what to delegate, or an existing task name/ID]"
---

# Delegate to Claude

Turn a request into a Todoist task that meets the delegation template, then give it the Claude label. The task is the whole brief: a worker with no memory of this conversation must be able to do it from the task alone.

## 1. Settings

Read `~/.config/todoist-agent/config.toml` if it exists. You need `labels.claude` (default `claude`), `folders.roots` (folders whose subfolders are projects), and `folders.projects` (Todoist project name → work folder). If the file is missing, use the defaults.

## 2. Fill the template

Build the description from `$ARGUMENTS` and the conversation:

```
**Goal:** <one or two sentences: what to do>
**Done when:** <what the finished result is, concretely: "a one-page comparison in markdown", "a branch with the fix and passing tests">
**Folder:** <absolute path where the work happens and its files go>
**Context:** <links, file paths, people, meeting names, Slack channels, anything that saves the worker from guessing>
**Stop before:** <where to stop, or leave the line out>
**Model:** <opus | sonnet | haiku, or leave the line out>
```

Rules:

- **Goal** and **Done when** are required and must be specific. If you can't fill them from what you know, ask the user (AskUserQuestion, one short round). Don't create a vague task.
- **Folder** is required: it's where the worker runs and where its files land. Pick it in this order:
  1. The work is about the project open in this session: the current working directory.
  2. The task belongs to a Todoist project in `folders.projects`: that folder.
  3. List the subfolders of each of `folders.roots` (`ls -d <root>/*/`) and pick the one that clearly fits. If two could fit, glance at their `CLAUDE.md` or README.
  4. Nothing fits: propose a new `<root>/<kebab-name>` (2–4 words, in the style of the existing folder names). Don't create it; the run does.

  If you picked by 3 or 4, confirm the folder with the user (AskUserQuestion, the best match first, a new folder as another option), in the same round as any other questions. If there are no roots and no match, ask for the path.
- **Context**: include what you already know from the conversation (paths, URLs, names). The worker can read Slack, meeting notes, docs, email, and the web on its own, so point it in the right direction rather than pasting everything.
- **Model**: leave it out unless the user asks for a specific model. The default is Opus at high effort.
- **Stop before**: the worker never sends, shares, deletes, or completes anything, whatever this line says. Use this line for extra limits, such as "outline only, no full draft" or "don't change the public API".

## 3. Create or convert

- **New task:** Todoist `add-tasks` with a short, verb-first `content` (title), the template as `description`, and `labels: [<claude label>]`. Put it in the Todoist project it belongs to (use `find-projects`), or the Inbox if unclear. Add a due date only if the user gave one.
- **Existing task** (the user named or linked one): fetch it with `find-tasks` or `fetch-object`. Keep the user's original description: put it under **Context** as "Original notes: …". Then call `update-tasks` with the new `description` and `labels` = its current labels plus the Claude label. `labels` replaces the whole list, so include the existing ones. If it carries the human label, remove it.

Don't set `projectId`, `sectionId`, or `parentId` when updating an existing task. Those fields move it.

## 4. Confirm

Reply in two or three lines: the task title with its link, its folder (say "new" if it doesn't exist yet), and "Run `/todoist-agent:run` to have Claude work the queue."
