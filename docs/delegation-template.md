# Delegating from other agents

Any agent that has the Todoist MCP connected (for example Claude on claude.ai, in a Project, or in Cowork) can queue work for Claude. Paste the block below into that agent's instructions, and change the label names if yours differ.

---

**Delegating to Claude through Todoist**

When I ask you to delegate something to Claude, "queue it for Claude", or "have Claude do it", create a Todoist task:

- **Title:** short and verb-first ("Draft Q4 planning memo").
- **Label:** `claude`. If you're converting an existing task, keep its other labels and remove `human` if it has it.
- **Description,** in exactly this form:

  ```
  **Goal:** <one or two sentences: what to do>
  **Done when:** <the concrete deliverable>
  **Folder:** <absolute path on my machine, or the name of one of my project folders; leave the line out if unknown>
  **Context:** <links, file paths, people, meetings, Slack channels: anything that saves guessing>
  **Stop before:** <extra limits, e.g. "outline only"; leave the line out if none>
  **Model:** <opus | sonnet | haiku; leave the line out unless I ask for one>
  ```

**Goal** and **Done when** are required and must be specific. Without a **Folder**, the run hands the task back asking which folder, so include it when you know it. If you can't fill them in from what I've told you, ask me instead of creating the task. Don't add due dates unless I give one.

Claude works the queue when I run `/relay:run`. The result comes back as a comment on the task, and the label switches to `human`.

---

The run step doesn't reject tasks that skip the template. A worker scopes whatever it gets, and if the task isn't clear enough it hands it back with questions. The template just makes a first-pass success much more likely.
