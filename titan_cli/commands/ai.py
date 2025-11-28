# titan_cli/commands/ai.py
import typer
import tomli
import tomli_w
from pathlib import Path

from ..core.config import TitanConfig
from ..core.secrets import SecretManager
from ..ui.components.typography import TextRenderer
from ..ui.components.spacer import SpacerRenderer
from ..ui.views.prompts import PromptsRenderer
from ..ui.views.menu_components.dynamic_menu import DynamicMenu
from ..ai.client import AIClient, PROVIDER_CLASSES
from ..ai.oauth_helper import OAuthHelper
from ..ai.constants import get_default_model, get_provider_name
from ..ai.models import AIRequest, AIMessage
from ..messages import msg


ai_app = typer.Typer(name="ai", help="Configure and manage AI providers.")


def _select_model(provider: str, prompts: PromptsRenderer, text: TextRenderer) -> str:
    """
    Interactive model selection with free input and visual suggestions.

    Args:
        provider: Provider key (anthropic, openai, gemini)
        prompts: PromptsRenderer instance
        text: TextRenderer instance

    Returns:
        Selected model name
    """
    spacer = SpacerRenderer()

    text.subtitle(f"Model Selection for {get_provider_name(provider)}")
    spacer.line()

    # Show popular models as reference (not exhaustive list)
    if provider == "anthropic":
        text.body("Popular Claude models:", style="dim")
        text.body("  • claude-3-5-sonnet-20241022 - Latest, balanced performance", style="dim")
        text.body("  • claude-3-opus-20240229 - Most capable, best for complex tasks", style="dim")
        text.body("  • claude-3-haiku-20240307 - Fastest, cost-effective", style="dim")
        text.body("  • claude-3-5-haiku-20241022 - New fast model", style="dim")

    elif provider == "openai":
        text.body("Popular OpenAI models:", style="dim")
        text.body("  • gpt-4-turbo - Latest GPT-4, best performance", style="dim")
        text.body("  • gpt-4 - Stable GPT-4", style="dim")
        text.body("  • gpt-3.5-turbo - Fast and cost-effective", style="dim")

    elif provider == "gemini":
        text.body("Popular Gemini models:", style="dim")
        text.body("  • gemini-1.5-pro - Latest pro model", style="dim")
        text.body("  • gemini-1.5-flash - Fast and efficient", style="dim")
        text.body("  • gemini-pro - Standard model", style="dim")

    spacer.line()
    text.body("💡 Tip: You can enter any model name, including custom/enterprise models", style="dim")
    spacer.line()

    # Free text input with sensible default
    default_model = get_default_model(provider)
    model = prompts.ask_text(
        "Enter model name (or press Enter for default)",
        default=default_model
    )

    return model or default_model


def _test_ai_connection(provider: str, secrets: SecretManager, model: str = None, base_url: str = None):
    """
    Internal helper to test AI provider connection.

    Args:
        provider: Provider key
        secrets: SecretManager instance
        model: Optional model name to test (uses provider's model if None)
        base_url: Optional custom endpoint URL
    """
    text = TextRenderer()

    model_info = f" with model '{model}'" if model else ""
    endpoint_info = f" (custom endpoint)" if base_url else ""
    text.info(f"Testing {provider} connection{model_info}{endpoint_info}...")

    try:
        provider_class = PROVIDER_CLASSES.get(provider)
        if not provider_class:
            raise ValueError(f"Unknown provider: {provider}")

        # Get API key
        api_key = secrets.get(f"{provider}_api_key")

        # Special case for Gemini OAuth
        if provider == "gemini" and secrets.get("gemini_oauth_enabled"):
             api_key = "GCLOUD_OAUTH"

        if not api_key:
            raise ValueError(f"API key for {provider} not found.")

        # Instantiate provider with model and base_url
        kwargs = {"api_key": api_key}
        if model:
            kwargs["model"] = model
        if base_url:
            kwargs["base_url"] = base_url

        provider_instance = provider_class(**kwargs)

        # Generate a simple test response
        test_request = AIRequest(
            messages=[AIMessage(role="user", content="Say 'Hello!' if you can hear me")],
            max_tokens=50
        )
        response = provider_instance.generate(test_request)

        text.success("✅ Connection successful!")
        text.body(f"Model: {response.model}", style="dim")
        text.body(f"Response: {response.content}", style="dim")

    except Exception as e:
        text.error(f"❌ Connection failed: {e}")
        return False

    return True

def configure_ai_interactive():
    """Interactive AI configuration workflow."""
    text = TextRenderer()
    prompts = PromptsRenderer(text_renderer=text)
    secrets = SecretManager()
    config = TitanConfig() # To read existing global config

    text.title("🤖 Configure AI Provider")
    text.line()

    # Step 1: Select Provider
    provider_menu = DynamicMenu(title="Select AI Provider", emoji="🤖")
    cat = provider_menu.add_category("Providers")
    cat.add_item(msg.AI.ANTHROPIC_LABEL, msg.AI.ANTHROPIC_DESCRIPTION_MODEL.format(model="claude-3-opus-20240229"), "anthropic")
    cat.add_item(msg.AI.OPENAI_LABEL, msg.AI.OPENAI_DESCRIPTION_MODEL.format(model="gpt-4-turbo"), "openai")
    cat.add_item(msg.AI.GEMINI_LABEL, msg.AI.GEMINI_DESCRIPTION_MODEL.format(model="gemini-1.5-pro"), "gemini")

    provider_choice = prompts.ask_menu(provider_menu.to_menu())
    if not provider_choice:
        text.warning(msg.Errors.OPERATION_CANCELLED)
        return

    provider = provider_choice.action
    text.line()

    # Step 2: Authentication
    auth_successful = False
    if provider == "gemini":
        text.info("Gemini can use OAuth via Google Cloud SDK.")
        use_oauth = prompts.ask_confirm("Use OAuth for Gemini authentication?", default=True)
        if use_oauth:
            helper = OAuthHelper()
            status = helper.check_gcloud_auth()
            if not status.available:
                text.error(f"Google Cloud SDK not found or not working: {status.error}")
                text.body(helper.get_install_instructions())
                return
            if not status.authenticated:
                text.warning("You are not authenticated with gcloud.")
                if prompts.ask_confirm("Run 'gcloud auth application-default login' now?"):
                    text.body(helper.get_auth_instructions())
                return # Exit if user doesn't want to authenticate now
            
            secrets.set("gemini_oauth_enabled", "true", scope="user")
            text.success("✅ Gemini configured to use Google Cloud OAuth.")
            auth_successful = True
        else: # User chose not to use OAuth, prompt for API key
             api_key = secrets.prompt_and_set(
                key="gemini_api_key",
                prompt_text="Enter your Gemini API key",
                scope="user"
            )
             if api_key:
                 secrets.delete("gemini_oauth_enabled", scope="user") # Ensure OAuth is not enabled
                 auth_successful = True
    else: # API Key flow for Anthropic/OpenAI
        key_name = f"{provider}_api_key"
        if secrets.get(key_name):
            text.info(f"API key already configured for {provider}.")
            if not prompts.ask_confirm("Do you want to replace the existing key?"):
                text.warning(msg.Errors.OPERATION_CANCELLED)
                return
        
        api_key = secrets.prompt_and_set(key=key_name, prompt_text=f"Enter your {provider.title()} API Key", scope="user")
        if api_key:
            auth_successful = True
    
    if not auth_successful:
        text.warning(msg.Errors.OPERATION_CANCELLED)
        return

    text.line()

    # Step 3: Custom Endpoint (Optional - for enterprise/corporate deployments)
    base_url = None
    if prompts.ask_confirm(
        "Do you use a custom API endpoint? (e.g., corporate proxy, AWS Bedrock)",
        default=False
    ):
        spacer = SpacerRenderer()
        spacer.line()
        text.info("Custom endpoints are used for:")
        text.body("  • Corporate/enterprise proxies", style="dim")
        text.body("  • AWS Bedrock", style="dim")
        text.body("  • Azure OpenAI", style="dim")
        text.body("  • Self-hosted deployments", style="dim")
        spacer.line()

        if provider == "anthropic":
            text.body("Example: https://bedrock-runtime.us-east-1.amazonaws.com", style="dim")
        elif provider == "openai":
            text.body("Example: https://your-instance.openai.azure.com", style="dim")

        spacer.line()
        base_url = prompts.ask_text(
            "Enter custom API endpoint URL",
            default=""
        )

        if base_url:
            text.success(f"✅ Will use custom endpoint: {base_url}")
        else:
            text.info("Using standard endpoint")

        text.line()

    # Step 4: Model Selection
    model = _select_model(provider, prompts, text)
    text.line()

    # Step 5: Save to global config
    global_config_path = TitanConfig.GLOBAL_CONFIG
    global_config = {}
    if global_config_path.exists():
        with open(global_config_path, "rb") as f:
            global_config = tomli.load(f)

    if "ai" not in global_config:
        global_config["ai"] = {}
    global_config["ai"]["provider"] = provider
    global_config["ai"]["model"] = model

    # Save base_url if provided
    if base_url:
        global_config["ai"]["base_url"] = base_url
    elif "base_url" in global_config.get("ai", {}):
        # Remove base_url if user didn't provide one (using standard endpoint)
        del global_config["ai"]["base_url"]

    with open(global_config_path, "wb") as f:
        tomli_w.dump(global_config, f)

    text.success(f"✅ AI provider configured:")
    text.body(f"  Provider: {get_provider_name(provider)}", style="dim")
    text.body(f"  Model: {model}", style="dim")
    if base_url:
        text.body(f"  Endpoint: {base_url}", style="dim")
    text.line()

    # Step 6: Test connection (optional)
    if prompts.ask_confirm("Test AI connection now?", default=True):
        test_success = _test_ai_connection(provider, secrets, model, base_url)
        if not test_success:
            text.line()
            text.warning("⚠️  Connection test failed. You may want to reconfigure.")
            if prompts.ask_confirm("Reconfigure now?", default=False):
                configure_ai_interactive()  # Recursive call to reconfigure

@ai_app.command("configure")
def configure():
    """Configure your AI provider interactively."""
    configure_ai_interactive()

@ai_app.command("test")
def test():
    """Test the connection to the configured AI provider."""
    config = TitanConfig()
    secrets = SecretManager()

    if not config.config.ai:
        typer.echo("❌ No AI provider configured. Run: titan ai configure")
        raise typer.Exit(1)

    provider = config.config.ai.provider
    model = config.config.ai.model if config.config.ai.model else None

    # Get base_url from config if exists
    base_url = None
    global_config_path = TitanConfig.GLOBAL_CONFIG
    if global_config_path.exists():
        with open(global_config_path, "rb") as f:
            global_config = tomli.load(f)
            base_url = global_config.get("ai", {}).get("base_url")

    _test_ai_connection(provider, secrets, model, base_url)
