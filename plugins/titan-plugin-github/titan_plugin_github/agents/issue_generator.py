from titan_cli.ai.agents.base import BaseAIAgent, AgentRequest, AIGenerator

class IssueGeneratorAgent(BaseAIAgent):
    def __init__(self, ai_client: AIGenerator):
        super().__init__(ai_client)

    def get_system_prompt(self) -> str:
        return """You are an expert at creating highly professional, descriptive, and useful GitHub issues.
Your task is to generate an issue title and a detailed, markdown-formatted description based on user input and an optional template.
Ensure the title follows the Conventional Commits specification (e.g., "feat(scope): brief description").
The language for both title and description must be English.
Prioritize clarity, conciseness, and actionable detail in the description.
If the user provides code snippets, you must include them in the description, properly formatted in markdown code blocks.
"""

    def generate_issue(self, user_description: str, template: str = None) -> (str, str):
        if template:
            prompt = f"""
            Here is a GitHub issue template:
            ---
            {template}
            ---
            Here is a description of the issue, which may include code snippets:
            ---
            {user_description}
            ---
            Please fill out the template with the provided information. If there are code snippets, include them in a "Code Snippets" section, formatted correctly with markdown.
            The final output should be in the format:
            TITLE: <conventional commit title>
            DESCRIPTION:
            <markdown-formatted description>
            """
        else:
            prompt = f"""
            Generate a GitHub issue title and a markdown-formatted description for the following content, which may include code snippets:
            ---
            {user_description}
            ---
            The title should follow the conventional commit format.
            The description should be well-structured, including a summary, a detailed description, and a "Code Snippets" section.
            CRITICAL: If the user provides code snippets, you MUST include them in the "Code Snippets" section, without any modification, formatted correctly with markdown.
            The final output should be in the format:
            TITLE: <conventional commit title>
            DESCRIPTION:
            <markdown-formatted description with a "Code Snippets" asection if code is provided>
            """
        
        request = AgentRequest(context=prompt)
        response = self.generate(request)

        if "DESCRIPTION:" in response.content:
            parts = response.content.split("DESCRIPTION:", 1)
            title = parts[0].replace("TITLE:", "").strip()
            body = parts[1].strip()
        else:
            title = response.content.splitlines()[0]
            body = response.content
            
        return title, body
