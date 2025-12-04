"""
Example: AI-Powered GitHub PR Review Workflow

This example demonstrates how to use TAP-powered AI agents to automatically
review GitHub pull requests.

Prerequisites:
- GitHub plugin configured
- AI client configured (Anthropic)
- GitHub token with repo access
"""

from pathlib import Path
from titan_cli.core.config import TitanConfig
from titan_cli.core.secrets import SecretManager
from titan_cli.engine import WorkflowEngine, WorkflowContextBuilder


def main():
    """
    Run an AI-powered PR review workflow.
    """
    # 1. Initialize Titan CLI
    config_path = Path.home() / ".titan" / "config.toml"
    titan_config = TitanConfig(config_path)
    secrets = SecretManager(titan_config)

    # 2. Create workflow context
    context = (
        WorkflowContextBuilder(config=titan_config, secrets=secrets)
        .with_ai()  # Enable AI client with TAP
        .with_ui()  # Enable UI for output
        .build()
    )

    # 3. Set PR to review
    pr_number = 123  # Replace with actual PR number
    context.data["pr_number"] = pr_number
    context.data["review_focus"] = "general"  # or 'security', 'performance'
    context.data["auto_comment"] = False  # Set to True to post comments automatically

    # 4. Get GitHub plugin steps
    github_plugin = context.config.registry.get_plugin("github")
    if not github_plugin or not github_plugin.is_available():
        print("❌ GitHub plugin not available")
        return

    steps = github_plugin.get_steps()
    review_pr_step = steps["review_pr"]

    # 5. Run the review
    print(f"🔍 Starting AI review of PR #{pr_number}...")
    print()

    result = review_pr_step(context)

    # 6. Display results
    if result.success:
        print("✅ Review completed successfully!")
        print()
        print("📊 Review Summary:")
        print("=" * 80)
        print(result.metadata.get("review_summary", "No summary available"))
        print("=" * 80)
        print()
        print(f"🔧 Tools used: {', '.join(result.metadata.get('tools_used', []))}")
        print(f"🔄 Iterations: {result.metadata.get('iterations', 0)}")

        if result.metadata.get('auto_commented'):
            print(f"💬 Review comment posted to PR #{pr_number}")
    else:
        print(f"❌ Review failed: {result.message}")


def example_security_review():
    """
    Example of security-focused PR review.
    """
    config_path = Path.home() / ".titan" / "config.toml"
    titan_config = TitanConfig(config_path)
    secrets = SecretManager(titan_config)

    context = (
        WorkflowContextBuilder(config=titan_config, secrets=secrets)
        .with_ai()
        .with_ui()
        .build()
    )

    pr_number = 123
    context.data["pr_number"] = pr_number
    context.data["auto_comment"] = True  # Auto-post security findings

    github_plugin = context.config.registry.get_plugin("github")
    steps = github_plugin.get_steps()

    print(f"🔒 Running security analysis on PR #{pr_number}...")
    result = steps["analyze_pr_security"](context)

    if result.success:
        print("✅ Security analysis complete")
        print(result.metadata.get("review_summary"))
    else:
        print(f"❌ Security analysis failed: {result.message}")


def example_performance_review():
    """
    Example of performance-focused PR review.
    """
    config_path = Path.home() / ".titan" / "config.toml"
    titan_config = TitanConfig(config_path)
    secrets = SecretManager(titan_config)

    context = (
        WorkflowContextBuilder(config=titan_config, secrets=secrets)
        .with_ai()
        .with_ui()
        .build()
    )

    pr_number = 123
    context.data["pr_number"] = pr_number

    github_plugin = context.config.registry.get_plugin("github")
    steps = github_plugin.get_steps()

    print(f"⚡ Running performance analysis on PR #{pr_number}...")
    result = steps["analyze_pr_performance"](context)

    if result.success:
        print("✅ Performance analysis complete")
        print(result.metadata.get("review_summary"))
    else:
        print(f"❌ Performance analysis failed: {result.message}")


def example_workflow_with_multiple_prs():
    """
    Example of batch PR review workflow.
    """
    config_path = Path.home() / ".titan" / "config.toml"
    titan_config = TitanConfig(config_path)
    secrets = SecretManager(titan_config)

    pr_numbers = [123, 124, 125]  # Replace with actual PR numbers

    print(f"🔍 Reviewing {len(pr_numbers)} pull requests...")
    print()

    for pr_num in pr_numbers:
        context = (
            WorkflowContextBuilder(config=titan_config, secrets=secrets)
            .with_ai()
            .with_ui()
            .build()
        )

        context.data["pr_number"] = pr_num
        context.data["review_focus"] = "general"
        context.data["auto_comment"] = False

        github_plugin = context.config.registry.get_plugin("github")
        steps = github_plugin.get_steps()

        print(f"📝 Reviewing PR #{pr_num}...")
        result = steps["review_pr"](context)

        if result.success:
            print(f"  ✅ PR #{pr_num} reviewed")
            print(f"  🔧 Tools used: {len(result.metadata.get('tool_calls', []))}")
        else:
            print(f"  ❌ PR #{pr_num} failed: {result.message}")
        print()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == "security":
            example_security_review()
        elif mode == "performance":
            example_performance_review()
        elif mode == "batch":
            example_workflow_with_multiple_prs()
        else:
            print(f"Unknown mode: {mode}")
            print("Usage: python github_pr_review_workflow.py [security|performance|batch]")
    else:
        main()
