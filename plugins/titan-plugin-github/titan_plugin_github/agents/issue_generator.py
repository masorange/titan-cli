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
"""

    def generate_issue(self, user_description: str, template: str = None) -> (str, str):
        if template:
            prompt = f"""
            Here is a GitHub issue template:
            ---
            {template}
            ---
            Here is a description of the issue:
            ---
            {user_description}
            ---
            Please fill out the template with the provided information.
            The final output should be in the format:
            TITLE: <conventional commit title>
            DESCRIPTION:
            <markdown-formatted description>
            """
        else:
            prompt = f"""
            Generate a GitHub issue title and a markdown-formatted description for the following content:
            ---
            {user_description}
            ---
            The title should follow the conventional commit format.
            The final output should be in the format:
            TITLE: <conventional commit title>
            DESCRIPTION:
            <markdown-formatted description>
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
