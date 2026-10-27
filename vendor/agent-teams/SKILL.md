---
name: agent-teams
description: Run multi-agent team collaboration inside DeepSeek Harness with the AgentTeams plugin 鈥?captain, members, tasks with dependencies, messaging, and quality gates. Use when a task is large enough to split across parallel agents, or when the user asks for a team, crew, or multi-agent workflow.
---

# AgentTeams for DeepSeek Harness

Multi-agent team collaboration plugin. Installed via
`dsh plugin --profile desktop add @nanmicoder/dsh-agent-teams@latest`
(npm package `@nanmicoder/dsh-agent-teams`, current version 0.1.25).

The plugin registers the `agent_teams_*` tools into the shared `tools`
registry and one usage section into the global system prompt, so **every
session of the profile can drive AgentTeams through natural language** 鈥?you do
not not need a special entry point.

## Tool surface

| Group | Tools |
|---|---|
| Lifecycle | `agent_teams_create`, `agent_teams_approve`, `agent_teams_delete`, `agent_teams_resume` |
| Roster | `agent_teams_add_member`, `agent_teams_remove_member` |
| Tasks | `agent_teams_create_task`, `agent_teams_claim_task`, `agent_teams_update_task`, `agent_teams_reassign_task`, `agent_teams_amend_task` |
| Coordination | `agent_teams_send_message`, `agent_teams_status`, `agent_teams_edit_plan` |

## Captain protocol (the important part)

1. **Inspect first.** Call `agent_teams_status` before creating anything.
   Continue existing work; never duplicate a roster or task list.
2. **Create with `approval="required"`** for a two-phase plan. Members and
   tasks stay unspawned/unclaimed until the user reviews and approves.
   Automatic approval requires an explicit request to run immediately.
3. **Build the whole DAG while staged.** For an ordinary research/audit plan,
   pass roster and dependency graph together in
   `agent_teams_create({plan:{members,tasks}})`. Every task needs a subject;
   pass `kind` and `assignee` explicitly when the plan specifies them.
4. **Present the plan and end your turn for review.** Never approve in the
   same turn that created or edited the plan.
5. **Delegate, do not duplicate.** The scheduler dispatches ready tasks after
   approval. Do not re-implement a member's work yourself.
6. **Yield while waiting.** Reports wake you automatically. Use
   `agent_teams_status` after a delivery or user request 鈥?never busy-poll.

## Task kinds and quality gates

| kind | requires |
|---|---|
| `work` | nothing (research, audits, general tasks) |
| `requirements` | objective + acceptance; completes only with `verdict=pass` |
| `implementation` | objective + acceptance + inScope + verify |
| `verification` | objective + acceptance + verify |
| `review` | objective + acceptance + `reviewedTaskId` |
| `repair` | objective + acceptance + inScope + verify + `sourceTaskId` |
| `integration` | objective + acceptance |

Full quality mode is
`requirements 鈫?implementation 鈫?verification 鈫?review 鈫?integration`.
A failed review automatically adds `repair` + the next review round and
rewires pending downstream gates 鈥?do not recreate that loop by hand.

## Attempt IDs

Tasks carry `attempt_id` capabilities. Always use the **current** attempt_id;
a stale one means ownership changed. `agent_teams_reassign_task` revokes the
old attempt and waits for quiescence 鈥?use it for retry, transfer, or takeover
rather than editing an active attempt.

## State on disk

Team state lives under `<session workspace>/.agent-teams/<teamId>/`:

```
team.json              roster + task graph
inbox/*.jsonl          per-member mailboxes
```

The state directory is configurable via the `stateDir` key in the plugin's
cordis row (default `.agent-teams`).

## Files on disk

```
<USER_HOME>\.dsh\profiles\desktop\node_modules\@nanmicoder\dsh-agent-teams\
  lib/index.js        host half 鈥?registers agent_teams_* tools
  lib/client.js       browser half 鈥?tree monitor in the web GUI
  cordis.patch.yml    mount declaration
  compatibility.json  declared dsh release compatibility
  scripts/doctor.mjs  diagnostics
```

## Notes and caveats

- `memberProvider` defaults to `spawn`; `fork` inherits completed lead turns.
- Halted means the user stopped work. Resume only on a later explicit user
  request, via `agent_teams_resume` or
  `create_task({resume:true, resumeReason})` 鈥?creating tasks alone never
  resumes.
- Escalated means the review loop hit its limit; it is **not** a halt.
- Deployment requires explicit user confirmation.
- Write-scope overlap between members is advisory, not a lock. Split write
  work into disjoint scopes and record them on shared tasks.
