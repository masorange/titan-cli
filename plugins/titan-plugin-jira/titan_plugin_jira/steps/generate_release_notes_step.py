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
        fields = issue.get("fields", {})
        key = issue.get("key", "")
        summary = fields.get("summary", "")
        description = fields.get("description", "")
        components = [c.get("name", "") for c in fields.get("components", [])]
        affected_brands = extract_affected_brands(issue)

        issue_data = {
            "key": key,
            "summary": summary,
            "description": description,
            "components": components,
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


def clean_summary(summary: str) -> str:
    """
    Clean JIRA summary by removing unwanted prefixes and technical noise.

    Examples of prefixes removed:
    - Platform: [iOS], [Android], [iOS/Android]
    - Brand: Yoigo:, Jazztel:, MASMOVIL:, etc.
    - Technical: FIX:, HOTFIX:, FEATURE:, BUGFIX:, etc.
    - Technical terms: "in class X", "method Y", "component Z"
    - Internal field IDs: customfield_XXXXX
    """
    import re

    # Remove ALL bracket prefixes at the start: [iOS], [Android], [E-999], [ECAPP-1234], etc.
    # Also removes multiple consecutive brackets: [Android] [Llamaya]
    # The + means "one or more" bracket patterns
    summary = re.sub(r'^(?:\[.*?\]\s*)+', '', summary)

    # Remove brand prefixes: "Yoigo:", "Jazztel:", "MASMOVIL:", etc.
    brand_names = ['Yoigo', 'MASMOVIL', 'Jazztel', 'Lycamobile', 'Lebara', 'Llamaya', 'Guuk', 'Sweno']
    for brand in brand_names:
        summary = re.sub(rf'^{brand}:\s*', '', summary, flags=re.IGNORECASE)

    # Remove technical prefixes: FIX:, HOTFIX:, FEATURE:, BUGFIX:, etc.
    summary = re.sub(r'^(?:FIX|HOTFIX|FEATURE|BUGFIX|REFACTOR|CHORE|FEAT|DOCS|STYLE|TEST|PERF):\s*', '', summary, flags=re.IGNORECASE)

    # Remove technical implementation details
    # "in class X", "in method Y", "in component Z"
    summary = re.sub(r'\s+in\s+(?:class|method|component|module|service|controller|manager)\s+\w+', '', summary, flags=re.IGNORECASE)

    # Remove parenthetical technical notes
    summary = re.sub(r'\s*\([^)]*(?:class|method|component|endpoint|API|field|model)[^)]*\)', '', summary, flags=re.IGNORECASE)

    # Remove "for developers", "internal", "backend", etc.
    summary = re.sub(r'\s*\((?:for developers|internal|backend|frontend|technical|dev only)\)', '', summary, flags=re.IGNORECASE)

    # Remove internal field IDs: customfield_XXXXX, bankAccount field, etc.
    summary = re.sub(r'\bcustomfield_\d+\b', 'internal field', summary, flags=re.IGNORECASE)
    summary = re.sub(r'\bbankAccount\s+field\b', 'bank account field', summary, flags=re.IGNORECASE)

    # Replace technical jargon with user-friendly English terms
    # (AI will translate these to proper Spanish with correct grammar)
    summary = re.sub(r'\banalytics\s+logger\b', 'analytics system', summary, flags=re.IGNORECASE)  # Specific pattern first
    summary = re.sub(r'\blogger\b', 'analytics system', summary, flags=re.IGNORECASE)
    summary = re.sub(r'\bendpoint\b', 'service', summary, flags=re.IGNORECASE)
    summary = re.sub(r'\bAPI\s+call\b', 'service call', summary, flags=re.IGNORECASE)
    summary = re.sub(r'\brefactor(?:ed|ing)?\b', 'improved', summary, flags=re.IGNORECASE)
    summary = re.sub(r'\bOTP\s+validation\b', 'OTP code validation', summary, flags=re.IGNORECASE)

    # Remove extra whitespace
    summary = ' '.join(summary.split())

    return summary.strip()


def generate_ai_descriptions(ctx: WorkflowContext, grouped_issues: Dict[str, List[Dict]]) -> Dict[str, str]:
    """Generate AI descriptions for unique issues."""
    from titan_cli.ai.models import AIMessage

    # Collect unique issues (with full context)
    unique_issues = {}
    for brand, issues in grouped_issues.items():
        for issue in issues:
            if issue["key"] not in unique_issues:
                cleaned_summary = clean_summary(issue["summary"])
                description = issue.get("description", "")
                components = issue.get("components", [])

                unique_issues[issue["key"]] = {
                    "summary": cleaned_summary,
                    "description": description[:500] if description else "",  # Limit to 500 chars
                    "components": ", ".join(components) if components else "N/A"
                }

    if not unique_issues:
        return {}

    # Build prompt with enhanced context
    issues_list = "\n\n".join([
        f"**{key}**\n"
        f"Summary: {data['summary']}\n"
        f"Description: {data['description'] or 'N/A'}\n"
        f"Components: {data['components']}"
        for key, data in unique_issues.items()
    ])

    system_prompt = """You are an expert at transforming technical JIRA issue summaries into user-friendly Spanish release notes for end users.

You will receive JIRA issues with:
- Summary (cleaned technical summary)
- Description (first 500 chars of issue description)
- Components (affected modules/areas)

Use ALL available context to produce accurate translations that reflect the true purpose of each change.

CRITICAL RULES:
1. TRANSLATE EVERYTHING TO SPANISH - Even if the input contains English words like "improved", "analytics system", "service", translate them properly
2. Use ONLY past participle form (participio pasado): "Modificados", "Actualizados", "Corregida", "Añadida", "Eliminado", "Mejorado"
3. Write for END USERS, not developers - focus on user-facing changes
4. Use gender/number agreement: "Corregida la visualización", "Actualizados los campos", "Añadida la pantalla", "Mejorado el sistema"
5. Remove ALL technical implementation details (class names, method names, internal IDs, technical jargon)
6. Keep descriptions SHORT and clear (max 15 words) - only what users need to know
7. USE THE DESCRIPTION AND COMPONENTS to understand the TRUE PURPOSE of the change - don't rely only on the summary

WHAT TO REMOVE:
- Platform tags: [iOS], [Android] - already removed
- Brand names: Yoigo:, Jazztel: - already removed
- Technical prefixes: FIX:, HOTFIX: - already removed
- Implementation details: "en la clase X", "método Y", "componente Z"
- Internal IDs: "customfield_X", "bankAccount field", specific field names
- Technical jargon: "endpoint", "API call", "refactor", "logger", "OTP validation"

WHAT TO KEEP:
- User-facing features: "nueva sección", "pantalla de autodiagnóstico"
- User-visible changes: "productos de televisión", "facturas devueltas"
- User benefits: "para permitir promociones adicionales", "para mejorar la conexión"

CORRECT EXAMPLES (based on real release notes):
- "Modificados los espacios promocionales para permitir promociones adicionales manuales"
- "Actualizados los campos en la llamada de smartWifi"
- "Corregida la visualización de los productos de televisión en tarifas y permanencias"
- "Actualizado el CI para compilar con Xcode 26"
- "Mejoras menores de rendimiento en iOS 26"
- "Añadida la visualización del enlace de 'Más información' en la pantalla de consentimientos OpenGateWay"
- "Corregido el bug que impedía cambiar el MSISDN con OTP en datos de contacto"
- "Eliminado el campo bankAccount por operaciones de mantenimiento"
- "Unificadas las claves con valores idénticos en POEditor"
- "Añadido el pago de facturas devueltas"
- "Añadida la pantalla de autodiagnóstico"

INCORRECT EXAMPLES (DO NOT USE):
- "Se añadió página..." (❌ preterite form)
- "Hemos mejorado..." (❌ present perfect)
- "Se implementó..." (❌ preterite form)
- "[iOS] Añadida página..." (❌ platform prefix)
- "Yoigo: Corregido bug..." (❌ brand prefix)
- "Actualizada la clase AuthManager para validar OTP" (❌ too technical - use: "Mejorada la validación de códigos OTP")
- "Eliminado el campo customfield_11931" (❌ internal ID - use: "Actualización de campos internos")
- "Refactorizado el logger de analíticas" (❌ technical - use: "Mejorado el sistema de analíticas")
- "improved the analytics system" (❌ English - use: "Mejorado el sistema de analíticas")
- "Update service configuration" (❌ English - use: "Actualizada la configuración del servicio")

TRANSLATION EXAMPLES (English → Spanish):
- "improved" → "Mejorado/Mejorada/Mejorados/Mejoradas" (with proper gender/number)
- "analytics system" → "sistema de analíticas"
- "service" → "servicio"
- "internal field" → "campo interno"
- "OTP code validation" → "validación de códigos OTP"

Return ONLY a JSON object mapping JIRA keys to Spanish descriptions. No explanations, no markdown, just pure JSON."""

    user_prompt = f"""Transform these JIRA issues into Spanish release note descriptions following the rules.

Use the Summary, Description, and Components to understand the TRUE PURPOSE of each change:

{issues_list}

Return format (ONLY JSON, no markdown):
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
            return {key: data["summary"] for key, data in unique_issues.items()}

        messages = [
            AIMessage(role="system", content=system_prompt),
            AIMessage(role="user", content=user_prompt)
        ]

        # Show loading indicator while AI processes (if Textual UI is available)
        if ctx.textual:
            with ctx.textual.loading("🤖 Generando descripciones con IA..."):
                response = ctx.ai.generate(messages, max_tokens=2000)
        else:
            # Fallback for non-Textual UI (legacy Rich UI)
            if ctx.ui:
                ctx.ui.text.info("🤖 Generando descripciones con IA...")
            response = ctx.ai.generate(messages, max_tokens=2000)

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
        return {key: data["summary"] for key, data in unique_issues.items()}


def format_markdown(grouped_issues: Dict[str, List[Dict]], descriptions: Dict[str, str]) -> str:
    """Format grouped issues into Markdown."""
    lines = []

    # Process ALL brands in fixed order (always show all brands)
    for emoji, brand in BRANDS_WITH_EMOJI:
        issues = grouped_issues.get(brand, [])

        lines.append(f"*{emoji} {brand}*")

        if not issues:
            # Show "Sin cambios" if no issues for this brand
            lines.append("- Sin cambios")
        else:
            # Show all issues for this brand
            for issue in issues:
                key = issue["key"]
                # Get AI description, fallback to cleaned summary if not available
                description = descriptions.get(key)
                if not description:
                    # Fallback: clean the original summary
                    description = clean_summary(issue["summary"])
                lines.append(f"- {description} ({key})")

        lines.append("")  # Empty line between brands

    # FILTRADO: No incluir "Marca Desconocida" en release notes
    # Estos issues no tienen marca asignada en JIRA y deben clasificarse manualmente
    # o corregirse en JIRA antes de incluirse en release notes
    #
    # unknown_issues = grouped_issues.get("Marca Desconocida", [])
    # if unknown_issues:
    #     emoji, brand = UNKNOWN_BRAND
    #     lines.append(f"*{emoji} {brand}*")
    #
    #     for issue in unknown_issues:
    #         key = issue["key"]
    #         description = descriptions.get(key)
    #         if not description:
    #             description = clean_summary(issue["summary"])
    #         lines.append(f"- {description} ({key})")
    #
    #     lines.append("")

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
