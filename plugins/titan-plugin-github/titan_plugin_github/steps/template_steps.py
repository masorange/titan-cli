import os
from titan_cli.engine.context import WorkflowContext
from titan_cli.engine.results import WorkflowResult, Success, Skip

def find_issue_template_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Find the GitHub issue template in the .github directory.
    """
    template_path = None
    if os.path.exists(".github/ISSUE_TEMPLATE.md"):
        template_path = ".github/ISSUE_TEMPLATE.md"
    elif os.path.exists(".github/issue_template.md"):
        template_path = ".github/issue_template.md"
    
    if template_path:
        with open(template_path, "r") as f:
            template = f.read()
        ctx.set("issue_template", template)
        return Success("Issue template found")
    
    return Skip("No issue template found")
