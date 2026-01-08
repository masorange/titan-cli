from titan_cli.ai.agents.base import BaseAIAgent, AgentRequest, AIGenerator

class IssueGeneratorAgent(BaseAIAgent):
    def __init__(self, ai_client: AIGenerator):
        super().__init__(ai_client)

    def get_system_prompt(self) -> str:
        return "You are an expert at creating GitHub issues. You can create issues from a description and a template."

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
            TITLE: <title>
            DESCRIPTION:
            <description>
            """
        else:
            prompt = f"""
            Generate a GitHub issue title and description for the following content:
            ---
            {user_description}
            ---
            The final output should be in the format:
            TITLE: <title>
            DESCRIPTION:
            <description>
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
