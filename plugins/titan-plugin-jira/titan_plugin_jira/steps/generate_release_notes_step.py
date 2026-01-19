"""
Generate multi-brand release notes from JIRA issues.
"""

import json
from typing import Dict, List, Any
from titan_cli.engine import WorkflowContext, WorkflowResult, Success, Error


# Brand configuration
BRANDS_WITH_EMOJI = [
    ("🟣", "Yoigo"),
    ("🟡", "MASMOVIL"),
    ("🔴", "Jazztel"),
    ("🔵", "Lycamobile"),
    ("🟤", "Lebara"),
    ("🟠", "Llamaya"),
    ("🟢", "Guuk"),
    ("⚪️", "Sweno"),
]

UNKNOWN_BRAND = ("⚫️", "Marca Desconocida")
BRANDS_FIELD_ID = "customfield_11931"


def extract_affected_brands(issue: Dict[str, Any]) -> List[str]:
    """Extract and normalize affected brands from JIRA issue."""
    brands_field = issue.get("fields", {}).get(BRANDS_FIELD_ID)
    affected_brands = []

    if not brands_field:
        return ["Marca Desconocida"]

    # Handle array of objects/strings
    if isinstance(brands_field, list):
        for brand_obj in brands_field:
            if isinstance(brand_obj, dict):
                brand_value = brand_obj.get("value") or brand_obj.get("name")
            else:
                brand_value = str(brand_obj)

            if brand_value:
                affected_brands.append(brand_value.strip())

    # Handle single object
    elif isinstance(brands_field, dict):
        brand_value = brands_field.get("value") or brands_field.get("name")
        if brand_value:
            affected_brands.append(brand_value.strip())

    # Handle string
    elif isinstance(brands_field, str):
        affected_brands = [b.strip() for b in brands_field.split(",") if b.strip()]

    if not affected_brands:
        return ["Marca Desconocida"]

    # Normalize "All" or "Todas"
    normalized = [b.lower() for b in affected_brands]
    if "all" in normalized or "todas" in normalized:
        return ["All"]

    return affected_brands


def group_issues_by_brand(issues: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, str]]]:
    """Group JIRA issues by affected brands."""
    grouped: Dict[str, List[Dict[str, str]]] = {brand: [] for _, brand in BRANDS_WITH_EMOJI}
    grouped["Marca Desconocida"] = []

    for issue in issues:
        key = issue.get("key", "")
        summary = issue.get("fields", {}).get("summary", "")
        affected_brands = extract_affected_brands(issue)

        issue_data = {
            "key": key,
            "summary": summary,
        }

        # If "All", add to all 8 brands
        if "All" in affected_brands:
            for _, brand in BRANDS_WITH_EMOJI:
                grouped[brand].append(issue_data.copy())

        # If "Marca Desconocida", add only there
        elif "Marca Desconocida" in affected_brands:
            grouped["Marca Desconocida"].append(issue_data)

        # Otherwise, add to specific brands
        else:
            for brand_name in affected_brands:
                brand_names = [b for _, b in BRANDS_WITH_EMOJI]
                if brand_name in brand_names:
                    grouped[brand_name].append(issue_data.copy())
                else:
                    # Unknown brand name -> Marca Desconocida
                    if issue_data not in grouped["Marca Desconocida"]:
                        grouped["Marca Desconocida"].append(issue_data)

    return grouped


def generate_ai_descriptions(ctx: WorkflowContext, grouped_issues: Dict[str, List[Dict]]) -> Dict[str, str]:
    """Generate AI descriptions for unique issues."""
    from titan_cli.ai.models import AIMessage

    # Collect unique issues
    unique_issues = {}
    for brand, issues in grouped_issues.items():
        for issue in issues:
            if issue["key"] not in unique_issues:
                unique_issues[issue["key"]] = issue["summary"]

    if not unique_issues:
        return {}

    # Build prompt
    issues_list = "\n".join([
        f"- {key}: {summary}"
        for key, summary in unique_issues.items()
    ])

    system_prompt = """You are an expert at transforming technical JIRA issue summaries into user-friendly Spanish release notes.

CRITICAL RULES:
1. Use ONLY past participle form (participio pasado): "Añadida", "Bloqueado", "Creado", "Corregidos"
2. Start with component/area: "Página de...", "Logger de...", "Funcionalidad de..."
3. Keep descriptions concise (max 10 words)
4. Avoid excessive technical terms
5. Use noun forms when appropriate: "Actualización de...", "Mejora en..."

CORRECT EXAMPLES:
- "Bloqueado el acceso al recargador a usuarios pospago"
- "Añadida nueva sección de consentimientos"
- "Creado logger de analíticas"
- "Corregidos errores en datos de contacto"
- "Actualización de claves OTP"

INCORRECT EXAMPLES (DO NOT USE):
- "Se añadió página..." (❌ preterite)
- "Hemos mejorado..." (❌ present perfect)
- "Se implementó..." (❌ preterite)

Return ONLY a JSON object mapping JIRA keys to Spanish descriptions. No explanations."""

    user_prompt = f"""Transform these JIRA summaries into Spanish release note descriptions following the rules:

{issues_list}

Return format:
{{
  "ECAPP-12154": "Bloqueado el acceso...",
  "ECAPP-12058": "Añadida nueva sección...",
  ...
}}"""

    try:
        if not ctx.ai:
            # Fallback to original summaries
            if ctx.ui:
                ctx.ui.text.warning("⚠️  AI not available, using original JIRA summaries")
            return {key: summary for key, summary in unique_issues.items()}

        messages = [AIMessage(role="user", content=user_prompt)]
        response = ctx.ai.generate(messages, system=system_prompt, max_tokens=2000)

        # Parse JSON response
        content = response.content.strip()

        # Remove markdown code blocks if present
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])

        ai_descriptions = json.loads(content)
        return ai_descriptions

    except Exception as e:
        if ctx.ui:
            ctx.ui.text.warning(f"⚠️  AI generation failed: {e}")
            ctx.ui.text.info("ℹ️  Using original JIRA summaries as fallback")

        # Fallback to original summaries
        return {key: summary for key, summary in unique_issues.items()}


def format_markdown(grouped_issues: Dict[str, List[Dict]], descriptions: Dict[str, str]) -> str:
    """Format grouped issues into Markdown."""
    lines = []

    # Process brands in fixed order
    for emoji, brand in BRANDS_WITH_EMOJI:
        issues = grouped_issues.get(brand, [])

        if not issues:
            continue

        lines.append(f"*{emoji} {brand}*")

        for issue in issues:
            key = issue["key"]
            description = descriptions.get(key, issue["summary"])
            lines.append(f"- {description} ({key})")

        lines.append("")  # Empty line between brands

    # Add Marca Desconocida section if exists
    unknown_issues = grouped_issues.get("Marca Desconocida", [])
    if unknown_issues:
        emoji, brand = UNKNOWN_BRAND
        lines.append(f"*{emoji} {brand}*")

        for issue in unknown_issues:
            key = issue["key"]
            description = descriptions.get(key, issue["summary"])
            lines.append(f"- {description} ({key})")

        lines.append("")

    return "\n".join(lines)


def generate_release_notes(ctx: WorkflowContext) -> WorkflowResult:
    """
    Generate multi-brand release notes from JIRA issues.

    Expected context data:
    - issues: List of JIRA issues from search step
    - fix_version: The fixVersion used for filtering

    Returns:
    - Success with markdown release notes
    """
    # Show header
    if ctx.views:
        ctx.views.step_header("generate_release_notes", ctx.current_step, ctx.total_steps)

    # Get issues from context
    issues = ctx.get("issues", [])
    fix_version = ctx.get("fix_version", "unknown")

    if not issues:
        return Error("No JIRA issues found to generate release notes")

    if ctx.ui:
        ctx.ui.text.info(f"📋 Processing {len(issues)} issues for version {fix_version}")

    # Group issues by brand
    grouped_issues = group_issues_by_brand(issues)

    # Count total issues per brand
    brand_counts = {brand: len(issues) for brand, issues in grouped_issues.items() if issues}

    if ctx.ui:
        ctx.ui.text.info(f"🏷️  Grouped into {len(brand_counts)} brands")

    # Generate AI descriptions
    if ctx.ui:
        ctx.ui.text.info("🤖 Generating AI descriptions...")

    descriptions = generate_ai_descriptions(ctx, grouped_issues)

    # Format as markdown
    markdown = format_markdown(grouped_issues, descriptions)

    # Display result
    if ctx.ui:
        ctx.ui.panel.print("\n" + markdown, panel_type="success", title=f"Release Notes - {fix_version}")
        ctx.ui.text.success("\n✅ Release notes generated successfully!")
        ctx.ui.text.info("📋 Copy the markdown above and paste it into your release notes")

    # Store in context
    ctx.set("release_notes", markdown)
    ctx.set("grouped_issues", grouped_issues)
    ctx.set("brand_counts", brand_counts)

    return Success(
        message=f"Generated release notes for {len(issues)} issues across {len(brand_counts)} brands",
        metadata={
            "fix_version": fix_version,
            "total_issues": len(issues),
            "brands": list(brand_counts.keys()),
            "markdown": markdown,
        }
    )
