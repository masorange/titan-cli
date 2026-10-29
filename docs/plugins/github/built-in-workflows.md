# GitHub Built-in Workflows

The GitHub plugin ships reusable workflows for PR creation, issue creation, and PR comment response.

## `create-pr-ai`

Creates a pull request after preparing branch state, pushing changes, and generating PR content with AI.

Set `params.draft` to control draft behavior:

- `true`: create as draft without prompting
- `false`: create as ready for review without prompting
- `null`: ask interactively before creating the PR

**Source workflow:** `plugins/titan-plugin-github/titan_plugin_github/workflows/create-pr-ai.yaml`

### Default flow

1. nested workflow `commit-ai`
2. `git.push`
3. `git.get_current_branch`
4. `git.show_branch_diff_summary`
5. `before_pr_generation` hook
6. `github.ai_suggest_pr_description`
7. `github.prompt_for_pr_draft`
8. `github.prompt_for_labels` (configured to save into `pr_labels`)
9. `before_push` hook
10. `github.create_pr`
11. `after_pr` hook

### Hooks

- `before_pr_generation`: inject project-specific context before AI generates PR content
- `before_push`: run validations before PR creation
- `after_pr`: notify or trigger post-creation automation

## `create-issue-ai`

Prompts for issue context, generates issue title and body with AI, then creates the GitHub issue.

**Source workflow:** `plugins/titan-plugin-github/titan_plugin_github/workflows/create-issue-ai.yaml`

### Default flow

1. `github.prompt_for_issue_body_step`
2. `github.ai_suggest_issue_title_and_body`
3. `github.prompt_for_self_assign`
4. `github.create_issue`

## `respond-pr-comments`

Helps a contributor review pending PR comments, switch to the PR branch, apply changes, reply, and request another review.

**Source workflow:** `plugins/titan-plugin-github/titan_plugin_github/workflows/respond-pr-comments.yaml`

### Default flow

1. `github.select_pr_for_review`
2. `github.fetch_pending_comments`
3. `github.check_clean_state`
4. `github.checkout_pr_branch`
5. `github.fetch_pr_review_bundle`
6. `github.build_change_manifest`
7. `github.judge_pr_comments`
8. `github.review_comments`
9. `after_review` hook
10. `github.push_commits`
11. `github.send_comment_replies`
12. `github.request_review`
13. `github.checkout_original_branch`

### How a comment is judged

Before anything is asked of you, one AI session reads the whole PR and decides about **every**
pending comment at once, and says for each one whether to change the code (`apply`), whether
the branch already does it (`already_done`), whether the comment is mistaken (`wrong`), or
whether it needs a human decision (`needs_discussion`) — with the files a fix would touch and
the **other places that use what would change**.

That session reads the repository you are on, plus material Titan writes into
`.titan-review/` at its root (the diff per file, each file's version before the PR, the PR
description and every comment). The directory is added to `.git/info/exclude`, so it stays out
of `git status` and out of your commits — `git commit -a` never stages untracked files.

Each verdict is shown with its reasoning, and you decide: let the AI make the change, change
it yourself, post the drafted reply (opened for editing first), write your own, or skip. When
the session cannot run — AI off for the `respond_pr_comment` task, no CLI, a failed call — the
comments are shown without verdicts and the workflow behaves as it did before.

An approved `apply` hands its verdict file to the interactive session that makes the change,
so it starts with the callers and the risk already worked out instead of eleven lines of diff.

### What the run records

Every run writes what it did to
`~/.titan/respond-comments/<repo>-pr<N>/runs/<run id>.json`: one row per comment
with its verdict, what you chose, whether that agreed with the verdict, and **the commit it
produced**. The same facts go to the log as `comment_decision` and `respond_comments_summary`,
next to `comment_judgement_session` and `comment_judgement_summary` (CLI, model, cost,
duration). It is written to disk as well because logs rotate.

The point of the commit column: when a later review of the same PR reports a problem,
`git blame` on that line gives a commit, and the record says which comment that commit was
answering — so a fix that answered its comment and broke something else is traceable instead
of being noticed by accident.

### Commit messages

Each fix is committed on its own. The subject line is written by AI from the diff that is
about to be committed, with the comment thread handed over as the intent, and the body names
the comment the commit answers and keeps the author attribution:

```
fix: Reject expired tokens before refreshing them

Addresses the review comment by @reviewer on src/auth.py:42.

By: reviewer
```

The subject is routed under the `commit_message` AI task, the same one the git plugin's
"Commit with AI" uses, so one preference in AI Configuration covers both. With AI off for that
task — or when no message can be generated — the commit falls back to `Fix: <filename>`.

### Hooks

- `after_review`: run lints, tests, or other checks before pushing replies

### Example extension

```yaml
extends: "plugin:github/respond-pr-comments"

hooks:
  after_review:
    - id: tests
      name: "Run Tests"
      command: "poetry run pytest"
      on_error: fail
```

## `resolve-pr-conflicts`

Un-conflicts one of your own pull requests: it checks out the PR's branch, merges the PR's base branch into it, hands the terminal to the interactive AI CLI to resolve the conflicts, offers to push so GitHub stops showing the PR as conflicting, and puts you back on the branch you started from.

The merge itself is `plugin:git/merge-branch`, run as a **nested** workflow rather than extended: a nested workflow's `Exit` — an aborted merge, nothing left to merge — comes back as `Success`, so the branch is restored either way. Extending it would let that `Exit` stop everything and leave you on the PR's branch.

**Source workflow:** `plugins/titan-plugin-github/titan_plugin_github/workflows/resolve-pr-conflicts.yaml`

### Parameters

| Param | Default | Meaning |
|-------|---------|---------|
| `conflict_pr_number` | `""` | PR to un-conflict. Empty asks among your open PRs that GitHub reports as conflicting. The `github` mod's **⚒ Resolve conflicts** button passes the PR it was pressed on. |
| `remote` | `"origin"` | Remote the branches are fetched from. |

### Default flow

1. `github.select_conflicted_pr` — picks the PR and lists the conflicting files, read with `git merge-tree`, which touches nothing
2. `github.check_clean_state` — exits before anything is touched if the working tree is dirty
3. `github.checkout_pr_branch` — saves the current branch and switches to the PR's
4. `plugin:git/merge-branch` (nested), given the PR's base branch as `source_branch`: the merge, the interactive AI session on the conflicts, the merge commit, and the push it asks about
5. `github.checkout_original_branch` — back to the branch you were on

### Behavior

- **GitHub can lag:** if the PR no longer conflicts by the time git is asked, the step says so and the merge proceeds as an ordinary one (or stops at "already up to date").
- **Declining the push** leaves the merge committed on the PR's branch; it is pushed by whatever you do next on it.
- **Quitting the TUI** mid-step unwinds the workflow with `WorkflowAborted`, and no later step runs: the branch is then left as it was at that moment.

## `fix-pr-checks`

Fixes the failing checks of one of your own pull requests: it reads the failed jobs' logs, checks out the PR's branch, opens an interactive AI session with those logs as its prompt, then offers to commit and push what the session changed, and puts you back on the branch you started from.

The pane's AI diagnosis says *why* a check failed; this is the other half, and the **✦ Fix with AI** button there starts it with that diagnosis already in hand.

**Source workflow:** `plugins/titan-plugin-github/titan_plugin_github/workflows/fix-pr-checks.yaml`

### Parameters

| Param | Default | Meaning |
|-------|---------|---------|
| `fix_pr_number` | `""` | PR to fix. Empty asks among your open PRs with a failing check. |
| `check_diagnosis` | `""` | What the pane already worked out, passed to the CLI as a hint it is told may be wrong. |
| `max_jobs` | `3` | How many failed jobs' logs are read into the prompt. The rest are named, not read. |

### Default flow

1. `github.select_failing_pr` — picks the PR, reads the failed jobs' logs and builds `check_fix_context`
2. `github.check_clean_state` — exits before anything is touched if the working tree is dirty
3. `github.checkout_pr_branch` — saves the current branch and switches to the PR's
4. `core.ai_code_assistant` — the interactive session, on the PR's branch, with the logs as its prompt
5. `plugin:git/commit-ai` (nested) — commits what changed with an AI message and pushes it; nested so that "nothing to commit" does not stop the workflow
6. `github.checkout_original_branch` — back to the branch you were on

### Behavior

- **The CLI is told not to commit:** the prompt asks it to fix and verify, and leaves committing to step 5, where you see the diff and the message first.
- **External CI:** a failed check that is not a GitHub Actions job has no log to read, so only its name reaches the prompt.
- **Checks already green:** if the PR has no failing check by the time it is asked, the workflow says so and exits.
