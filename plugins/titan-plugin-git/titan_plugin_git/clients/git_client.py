# plugins/titan-plugin-git/titan_plugin_git/clients/git_client.py
import subprocess
import re
import shutil # Added for shutil.which
from typing import List, Optional, Tuple
from datetime import datetime

from ..models import GitBranch, GitStatus
from ..exceptions import (
    GitError,
    GitClientError,
    GitCommandError,
    GitBranchNotFoundError,
    GitDirtyWorkingTreeError,
    GitNotRepositoryError,
    GitMergeConflictError
)
from ..messages import msg


class GitClient:
    """
    Git client using subprocess

    Wraps git commands and provides a Pythonic interface.

    Examples:
        >>> client = GitClient()
        >>> branch = client.get_current_branch()
        >>> print(branch)
        'develop'
    """

    def __init__(
        self,
        repo_path: str = ".",
        main_branch: str = "main",
        default_remote: str = "origin"
    ):
        """
        Initialize Git client

        Args:
            repo_path: Path to git repository (default: current directory)
            main_branch: Main branch name (from config)
            default_remote: Default remote name (from config)
        """
        self.repo_path = repo_path
        self.main_branch = main_branch
        self.default_remote = default_remote
        self._original_branch: Optional[str] = None
        self._stash_message: Optional[str] = None
        self._stashed: bool = False
        self._check_git_installed() # Check git installation here
        self._check_repository()

    def _check_git_installed(self) -> None:
        """Check if git CLI is installed."""
        if not shutil.which("git"):
            raise GitClientError(msg.Git.CLI_NOT_FOUND)

    def _check_repository(self) -> None:
        """Check if current directory is a git repository"""
        try:
            self._run_command(["git", "rev-parse", "--is-inside-work-tree"], check=False) # More robust check
        except GitCommandError:
            raise GitNotRepositoryError(msg.Git.NOT_A_REPOSITORY.format(repo_path=self.repo_path))

    def _run_command(self, args: List[str], check: bool = True) -> str:
        """
        Run git command and return stdout

        Args:
            args: Command arguments (including 'git')
            check: Raise exception on error

        Returns:
            Command stdout as string

        Raises:
            GitCommandError: If command fails
            GitNotRepositoryError: If not in a git repository
        """
        try:
            result = subprocess.run(
                args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=check
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            if "not a git repository" in error_msg:
                raise GitNotRepositoryError(msg.Git.NOT_A_REPOSITORY.format(repo_path=self.repo_path))
            raise GitCommandError(msg.Git.COMMAND_FAILED.format(error_msg=error_msg)) from e
        except FileNotFoundError:
            raise GitClientError(msg.Git.CLI_NOT_FOUND) # Should be caught by _check_git_installed, but safety
        except Exception as e:
            raise GitError(msg.Git.UNEXPECTED_ERROR.format(e=e)) from e

    def get_current_branch(self) -> str:
        """
        Get current branch name

        Returns:
            Current branch name
        """
        return self._run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])

    def get_current_commit(self) -> str:
        """
        Get current commit SHA (HEAD)

        Returns:
            Full SHA of current commit
        """
        return self._run_command(["git", "rev-parse", "HEAD"])

    def get_commit_sha(self, ref: str) -> str:
        """
        Get commit SHA for any git ref (branch, tag, remote branch, etc.)

        Args:
            ref: Git reference (e.g., "HEAD", "develop", "origin/main", "v1.0.0")

        Returns:
            Full SHA of the commit
        """
        return self._run_command(["git", "rev-parse", ref])

    def get_status(self) -> GitStatus:
        """
        Get repository status

        Returns:
            GitStatus object
        """
        branch = self.get_current_branch()

        status_output = self._run_command(["git", "status", "--short"])

        modified = []
        untracked = []
        staged = []

        for line in status_output.splitlines():
            if not line.strip():
                continue

            status_code = line[:2]
            file_path = line[3:].strip()

            if status_code[0] != ' ' and status_code[0] != '?':
                staged.append(file_path)

            if status_code[1] == 'M':
                modified.append(file_path)
            elif status_code == '??':
                untracked.append(file_path)

        is_clean = not (modified or untracked or staged)

        ahead, behind = self._get_upstream_status()

        return GitStatus(
            branch=branch,
            is_clean=is_clean,
            modified_files=modified,
            untracked_files=untracked,
            staged_files=staged,
            ahead=ahead,
            behind=behind
        )

    def _get_upstream_status(self) -> Tuple[int, int]:
        """Get commits ahead/behind upstream"""
        try:
            output = self._run_command(
                ["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"],
                check=False
            )
            if output:
                # Output might be empty if no upstream or no diff
                parts = output.split()
                if len(parts) == 2:
                    return int(parts[0]), int(parts[1])
        except GitCommandError:
            # No upstream configured
            pass
        return 0, 0

    def checkout(self, branch: str) -> None:
        """
        Checkout a branch

        Args:
            branch: Branch name to checkout

        Raises:
            GitBranchNotFoundError: If branch doesn't exist
            GitDirtyWorkingTreeError: If working tree is dirty
        """
        # Check if branch exists locally or remotely
        try:
            self._run_command(["git", "show-ref", "--verify", f"refs/heads/{branch}"], check=False)
            self._run_command(["git", "show-ref", "--verify", f"refs/remotes/origin/{branch}"], check=False)
        except GitCommandError: # if both fail, it means it doesn't exist
            raise GitBranchNotFoundError(msg.Git.BRANCH_NOT_FOUND.format(branch=branch))

        # Checkout
        try:
            self._run_command(["git", "checkout", branch])
        except GitCommandError as e:
            if msg.Git.UNCOMMITTED_CHANGES_OVERWRITE_KEYWORD in e.stderr: # Access stderr from raised exception
                raise GitDirtyWorkingTreeError(
                    msg.Git.CANNOT_CHECKOUT_UNCOMMITTED_CHANGES
                )
            raise

    def update_branch(self, branch: str, remote: Optional[str] = None) -> None:
        """
        Update branch from remote (fetch + merge --ff-only)

        Args:
            branch: Branch to update
            remote: Remote name (defaults to configured default_remote)
        """
        remote = remote or self.default_remote
        current = self.get_current_branch()

        if current != branch:
            self.checkout(branch)

        self._run_command(["git", "fetch", remote, branch])

        try:
            self._run_command(["git", "merge", "--ff-only", f"{remote}/{branch}"])
        except GitCommandError as e:
            if msg.Git.MERGE_CONFLICT_KEYWORD in e.stderr:
                raise GitMergeConflictError(msg.Git.MERGE_CONFLICT_WHILE_UPDATING.format(branch=branch))
            raise

        if current != branch:
            self.checkout(current)

    def get_branches(self, remote: bool = False) -> List[GitBranch]:
        """
        List branches

        Args:
            remote: List remote branches instead of local

        Returns:
            List of GitBranch objects
        """
        args = ["git", "branch"]
        if remote:
            args.append("-r")
        else:
            args.append("-l") # Explicitly list local branches

        output = self._run_command(args)

        branches = []
        for line in output.splitlines():
            is_current = line.startswith("*")
            name = line[2:].strip() if is_current else line.strip()

            if name.startswith("origin/HEAD"): # Skip 'origin/HEAD -> origin/main' type refs
                continue

            is_remote = remote
            upstream = None

            # Try to get upstream if local branch
            if not remote and is_current:
                try:
                    upstream_output = self._run_command([
                        "git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"
                    ])
                    upstream = upstream_output.strip()
                except GitCommandError:
                    pass # No upstream configured

            branches.append(GitBranch(
                name=name,
                is_current=is_current,
                is_remote=is_remote,
                upstream=upstream
            ))

        return branches

    def create_branch(self, branch_name: str, start_point: str = "HEAD") -> None:
        """
        Create a new branch

        Args:
            branch_name: Name for new branch
            start_point: Starting point (commit/branch)
        """
        self._run_command(["git", "branch", branch_name, start_point])

    def commit(self, message: str, all: bool = False, no_verify: bool = True) -> str:
        """
        Create a commit

        Args:
            message: Commit message
            all: Stage all modified and new files (`git add --all`)
            no_verify: Skip pre-commit and commit-msg hooks

        Returns:
            Commit hash
        """
        if all:
            # Stage all changes, including new files.
            self._run_command(["git", "add", "--all"])

        args = ["git", "commit", "-m", message]
        if no_verify:
            args.append("--no-verify")
        self._run_command(args)

        return self._run_command(["git", "rev-parse", "HEAD"])

    def get_commits_vs_base(self) -> List[str]:
        """
        Get commit messages from base branch to HEAD

        Returns:
            List of commit messages
        """
        result = self._run_command([
            "git", "log", "--oneline",
            f"{self.main_branch}..HEAD",
            "--pretty=format:%s"
        ])

        if not result:
            return []

        return [line.strip() for line in result.split('\n') if line.strip()]

    def update_from_main(self) -> None:
        """
        Update current branch from the configured main branch.
        """
        self.update_branch(self.main_branch, self.default_remote)

    def safe_delete_branch(self, branch: str, force: bool = False) -> bool:
        """
        Delete branch if not protected.
        
        Args:
            branch: Branch name to delete
            force: Force deletion (git branch -D)
        
        Returns:
            True if deleted, False if protected
        
        Raises:
            GitError: if branch is protected
        """
        if self.is_protected_branch(branch):
            raise GitError(msg.Git.BRANCH_PROTECTED.format(branch=branch))

        delete_arg = "-D" if force else "-d"
        self._run_command(["git", "branch", delete_arg, branch])
        return True

    def push(self, remote: str = "origin", branch: Optional[str] = None, set_upstream: bool = False, tags: bool = False) -> None:
        """
        Push to remote

        Args:
            remote: Remote name
            branch: Branch to push (default: current)
            set_upstream: Set upstream tracking
            tags: Push tags to remote (use --tags flag)
        """
        args = ["git", "push"]

        if set_upstream:
            args.append("-u")

        if tags:
            args.append("--tags")

        args.append(remote)

        if branch:
            args.append(branch)

        self._run_command(args)

    def pull(self, remote: str = "origin", branch: Optional[str] = None) -> None:
        """
        Pull from remote

        Args:
            remote: Remote name
            branch: Branch to pull (default: current)
        """
        args = ["git", "pull", remote]

        if branch:
            args.append(branch)

        self._run_command(args)

    def fetch(self, remote: str = "origin", branch: Optional[str] = None, all: bool = False) -> None:
        """
        Fetch from remote

        Args:
            remote: Remote name
            branch: Specific branch to fetch (optional)
            all: Fetch from all remotes
        """
        args = ["git", "fetch"]

        if all:
            args.append("--all")
        else:
            args.append(remote)
            if branch:
                args.append(branch)

        self._run_command(args)

    def has_uncommitted_changes(self) -> bool:
        """
        Check if there are uncommitted changes

        Returns:
            True if there are uncommitted changes
        """
        # git status --porcelain will output if there are any changes (staged or unstaged)
        status_output = self._run_command(["git", "status", "--porcelain"], check=False)
        return bool(status_output.strip())

    def stash_push(self, message: Optional[str] = None) -> bool:
        """
        Stash uncommitted changes

        Args:
            message: Optional stash message

        Returns:
            True if stash was created
        """

        if not message:
            message = msg.Git.AUTO_STASH_MESSAGE.format(timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        try:
            self._run_command(["git", "stash", "push", "-m", message])
            self._stashed = True
            self._stash_message = message
            return True
        except GitCommandError:
            return False

    def stash_pop(self, stash_ref: Optional[str] = None) -> bool:
        """
        Pop stash (apply and remove)

        Args:
            stash_ref: Optional stash reference (default: latest)

        Returns:
            True if stash was applied successfully
        """
        try:
            args = ["git", "stash", "pop"]
            if stash_ref:
                args.append(stash_ref)

            self._run_command(args)
            return True
        except GitCommandError:
            return False

    def find_stash_by_message(self, message: str) -> Optional[str]:
        """
        Find stash by message

        Args:
            message: Stash message to search for

        Returns:
            Stash reference (e.g., "stash@{0}") or None
        """
        try:
            output = self._run_command(["git", "stash", "list"])

            for line in output.splitlines():
                if message in line:
                    stash_ref = line.split(':')[0].strip()
                    return stash_ref

            return None
        except GitCommandError:
            return None

    def restore_stash(self) -> bool:
        """
        Restore stash created by this client

        Returns:
            True if stash was restored successfully
        """
        if not self._stashed or not self._stash_message:
            return True

        stash_ref = self.find_stash_by_message(self._stash_message)

        if stash_ref:
            if self.stash_pop(stash_ref):
                self._stashed = False
                self._stash_message = None
                return True
            else:
                return False
        else:
            return False

    def safe_checkout(self, branch: str, auto_stash: bool = True) -> bool:
        """
        Checkout branch safely with auto-stash

        Args:
            branch: Branch to checkout
            auto_stash: Automatically stash changes if needed

        Returns:
            True if checkout was successful

        Raises:
            GitDirtyWorkingTreeError: If changes exist and auto_stash is False
        """
        if not self._original_branch:
            self._original_branch = self.get_current_branch()

        current = self.get_current_branch()

        if current == branch:
            return True

        if self.has_uncommitted_changes():
            if not auto_stash:
                raise GitDirtyWorkingTreeError(
                    msg.Git.CANNOT_CHECKOUT_UNCOMMITTED_CHANGES_EXIST.format(branch=branch)
                )

            message = msg.Git.SAFE_SWITCH_STASH_MESSAGE.format(current=current, branch=branch)
            if not self.stash_push(message):
                raise GitDirtyWorkingTreeError(
                    msg.Git.STASH_FAILED_BEFORE_CHECKOUT
                )

        try:
            self.checkout(branch)
            return True
        except Exception:
            if self._stashed:
                self.restore_stash()
            raise

    def return_to_original_branch(self) -> bool:
        """
        Return to original branch and restore stash

        Returns:
            True if successfully returned
        """
        if not self._original_branch:
            return True

        current = self.get_current_branch()

        if current == self._original_branch:
            if self._stashed:
                return self.restore_stash()
            return True

        try:
            self.checkout(self._original_branch)

            if self._stashed:
                self.restore_stash()

            self._original_branch = None

            return True
        except Exception:
            return False

    def branch_exists_on_remote(self, branch: str, remote: str = "origin") -> bool:
        """
        Check if a branch exists on remote

        Args:
            branch: Branch name to check
            remote: Remote name (default: "origin")

        Returns:
            True if branch exists on remote, False otherwise
        """
        try:
            result = self._run_command([
                "git", "ls-remote", "--heads", remote, branch
            ], check=False) # check=False because ls-remote returns 1 if branch not found
            return bool(result.strip())
        except GitCommandError:
            return False

    def count_commits_ahead(self, base_branch: str = "develop") -> int:
        """
        Count how many commits current branch is ahead of base branch

        Args:
            base_branch: Base branch to compare against (default: "develop")

        Returns:
            Number of commits ahead
        """
        try:
            result = self._run_command([
                "git", "rev-list", "--count", f"{base_branch}..HEAD"
            ])
            return int(result.strip())
        except (GitCommandError, ValueError):
            return 0

    def count_unpushed_commits(self, branch: Optional[str] = None, remote: str = "origin") -> int:
        """
        Count how many commits are unpushed to remote

        Args:
            branch: Branch name (default: current branch)
            remote: Remote name (default: "origin")

        Returns:
            Number of unpushed commits, or 0 if branch doesn't have upstream
        """
        try:
            if branch is None:
                branch = self.get_current_branch()

            result = self._run_command([
                "git", "rev-list", "--count", f"{remote}/{branch}..HEAD"
            ])
            return int(result.strip())
        except (GitCommandError, ValueError):
            return 0

    def get_diff(self, base_ref: str, head_ref: str = "HEAD") -> str:
        """
        Get diff between two references

        Args:
            base_ref: Base reference (branch, commit, tag)
            head_ref: Head reference (default: "HEAD")

        Returns:
            Diff output as string
        """
        try:
            # git diff can return a non-zero exit code if there are differences,
            # so we use check=False and handle the output.
            return self._run_command(
                ["git", "diff", f"{base_ref}...{head_ref}"],
                check=False
            )
        except GitCommandError:
            # This might be raised for other reasons, returning empty is safe.
            return ""

    def get_uncommitted_diff(self) -> str:
        """
        Get diff of all uncommitted changes (staged + unstaged + untracked).

        Uses git add --intent-to-add to make untracked files visible in the diff
        without actually staging their content.

        Returns:
            Diff output as string
        """
        try:
            # Add untracked files to index without staging content
            # This makes new files visible to git diff HEAD
            self._run_command(["git", "add", "--intent-to-add", "."], check=False)

            # git diff HEAD shows all changes vs last commit (staged + unstaged + untracked)
            return self._run_command(["git", "diff", "HEAD"], check=False)
        except GitCommandError:
            return ""

    def get_staged_diff(self) -> str:
        """
        Get diff of staged changes only (index vs HEAD).

        Returns:
            Diff output as string
        """
        try:
            # git diff --cached shows only staged changes
            return self._run_command(["git", "diff", "--cached"], check=False)
        except GitCommandError:
            return ""

    def get_unstaged_diff(self) -> str:
        """
        Get diff of unstaged changes only (working directory vs index).

        Returns:
            Diff output as string
        """
        try:
            # git diff shows only unstaged changes
            return self._run_command(["git", "diff"], check=False)
        except GitCommandError:
            return ""

    def get_file_diff(self, file_path: str) -> str:
        """
        Get diff for a specific file.

        Args:
            file_path: Path to the file

        Returns:
            Diff output as string
        """
        try:
            return self._run_command(["git", "diff", "HEAD", "--", file_path], check=False)
        except GitCommandError:
            return ""

    def get_branch_diff(self, base_branch: str, head_branch: str) -> str:
        """
        Get diff between two branches.

        Args:
            base_branch: Base branch name (will be compared against origin/{base_branch})
            head_branch: Head branch name

        Returns:
            Diff output as string
        """
        try:
            # Always compare against remote to ensure we're comparing against latest
            return self._run_command(
                ["git", "diff", f"{self.default_remote}/{base_branch}...{head_branch}"],
                check=False
            )
        except GitCommandError:
            return ""

    def get_uncommitted_diff_stat(self) -> str:
        """
        Get diff stat summary of uncommitted changes (git diff --stat HEAD).

        Returns a summary showing files changed, insertions, and deletions.

        Returns:
            Diff stat output as string
        """
        try:
            return self._run_command(["git", "diff", "--stat", "HEAD"], check=False)
        except GitCommandError:
            return ""

    def get_branch_diff_stat(self, base_branch: str, head_branch: str) -> str:
        """
        Get diff stat summary between two branches.

        Args:
            base_branch: Base branch name (will be compared against origin/{base_branch})
            head_branch: Head branch name

        Returns:
            Diff stat output as string
        """
        try:
            # Always compare against remote to ensure we're comparing against latest
            return self._run_command(
                ["git", "diff", "--stat", f"{self.default_remote}/{base_branch}...{head_branch}"],
                check=False
            )
        except GitCommandError:
            return ""

    def get_branch_commits(self, base_branch: str, head_branch: str) -> list[str]:
        """
        Get list of commits in head_branch that are not in base_branch.

        Args:
            base_branch: Base branch name (will be compared against origin/{base_branch})
            head_branch: Head branch name

        Returns:
            List of commit messages
        """
        try:
            # Always compare against remote to ensure we're comparing against latest
            output = self._run_command([
                "git", "log",
                f"{self.default_remote}/{base_branch}..{head_branch}",
                "--pretty=format:%s"
            ])
            if output.strip():
                return output.strip().split("\n")
            return []
        except GitCommandError:
            return []

    def get_github_repo_info(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Extracts GitHub repository owner and name from the 'origin' remote URL.

        Returns:
            A tuple containing (repo_owner, repo_name) if detected, otherwise (None, None).
        """
        try:
            url = self._run_command(["git", "remote", "get-url", "origin"])

            # Parse: git@github.com:owner/repo.git or https://github.com/owner/repo.git
            match = re.search(r'github\.com[:/]([^/]+)/([^/.]+)', url)
            if match:
                return match.group(1), match.group(2)
        except GitCommandError:
            # Command failed, likely no remote 'origin' or not a git repo
            pass
        return None, None

    def create_tag(self, tag_name: str, message: str, ref: str = "HEAD") -> None:
        """
        Create an annotated tag

        Args:
            tag_name: Name of the tag
            message: Tag annotation message
            ref: Reference to tag (default: HEAD)

        Raises:
            GitCommandError: If tag creation fails
        """
        self._run_command(["git", "tag", "-a", tag_name, "-m", message, ref])

    def delete_tag(self, tag_name: str) -> None:
        """
        Delete a local tag

        Args:
            tag_name: Name of the tag to delete

        Raises:
            GitCommandError: If tag deletion fails
        """
        self._run_command(["git", "tag", "-d", tag_name])

    def tag_exists(self, tag_name: str) -> bool:
        """
        Check if a tag exists locally

        Args:
            tag_name: Name of the tag to check

        Returns:
            True if tag exists, False otherwise
        """
        try:
            self._run_command(["git", "tag", "-l", tag_name], check=False)
            tags = self._run_command(["git", "tag", "-l", tag_name]).strip()
            return tags == tag_name
        except GitCommandError:
            return False

    def list_tags(self) -> List[str]:
        """
        List all tags in the repository

        Returns:
            List of tag names
        """
        try:
            output = self._run_command(["git", "tag", "-l"])
            if output.strip():
                return [tag.strip() for tag in output.split('\n') if tag.strip()]
            return []
        except GitCommandError:
            return []

    def is_protected_branch(self, branch: str) -> bool:
        """
        Check if a branch is protected (main, master, develop, etc.)

        Args:
            branch: Branch name to check

        Returns:
            True if branch is protected
        """
        protected_branches = ["main", "master", "develop", "production", "staging"]
        return branch.lower() in protected_branches

    # ===== Worktree Operations =====

    def create_worktree(self, path: str, branch: str, create_branch: bool = False) -> None:
        """
        Create a new worktree at the specified path.

        Args:
            path: Path where to create the worktree
            branch: Branch to checkout in the worktree
            create_branch: If True, create the branch (git worktree add -b)

        Raises:
            GitCommandError: If worktree creation fails
        """
        args = ["git", "worktree", "add"]

        if create_branch:
            args.extend(["-b", branch])

        args.append(path)

        if not create_branch:
            args.append(branch)

        self._run_command(args)

    def remove_worktree(self, path: str, force: bool = False) -> None:
        """
        Remove a worktree.

        Args:
            path: Path to the worktree to remove
            force: Force removal even if worktree is dirty

        Raises:
            GitCommandError: If worktree removal fails
        """
        args = ["git", "worktree", "remove", path]

        if force:
            args.append("--force")

        self._run_command(args)

    def list_worktrees(self) -> List[dict]:
        """
        List all worktrees.

        Returns:
            List of dictionaries with worktree info (path, branch, commit)
        """
        try:
            output = self._run_command(["git", "worktree", "list", "--porcelain"])

            worktrees = []
            current_worktree = {}

            for line in output.splitlines():
                line = line.strip()
                if not line:
                    if current_worktree:
                        worktrees.append(current_worktree)
                        current_worktree = {}
                    continue

                if line.startswith("worktree "):
                    current_worktree["path"] = line.split("worktree ", 1)[1]
                elif line.startswith("HEAD "):
                    current_worktree["commit"] = line.split("HEAD ", 1)[1]
                elif line.startswith("branch "):
                    current_worktree["branch"] = line.split("branch ", 1)[1].replace("refs/heads/", "")
                elif line == "bare":
                    current_worktree["bare"] = True
                elif line == "detached":
                    current_worktree["detached"] = True

            # Add last worktree if exists
            if current_worktree:
                worktrees.append(current_worktree)

            return worktrees
        except GitCommandError:
            return []

    def run_in_worktree(self, worktree_path: str, args: List[str]) -> str:
        """
        Run a git command in a specific worktree.

        Args:
            worktree_path: Path to the worktree
            args: Command arguments (including 'git')

        Returns:
            Command stdout as string

        Raises:
            subprocess.CalledProcessError: If command fails (with stderr in exception)
        """
        # Use git -C <path> to run command in worktree
        if args[0] == "git":
            args = ["git", "-C", worktree_path] + args[1:]

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            # Re-raise with stderr attached for better error messages
            # stderr is already a string (text=True)
            raise subprocess.CalledProcessError(
                e.returncode,
                e.cmd,
                output=e.stdout,
                stderr=e.stderr
            )