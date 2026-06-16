"""Upload terms and translations to PoEditor step."""

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult

from ..messages import msg


def upload_terms_step(ctx: WorkflowContext) -> WorkflowResult:
    """Upload terms and translations to a PoEditor project.

    Inputs (from ctx.data):
        selected_project_id (str): PoEditor project ID
        terms_map (dict[str, str]): Dict mapping term keys to source language values
        translations_by_language (dict[str, dict[str, str]]): Dict mapping language codes to translations

    Optional inputs:
        source_language (str): Source language code (default: "en")

    Outputs (saved to ctx.data):
        terms_added (int): Number of terms added
        languages_updated (int): Number of languages updated

    Returns:
        Success: If upload completed successfully
        Error: If upload failed or required data is missing
    """
    if not ctx.textual:
        return Error("Textual UI context is not available")

    if not ctx.poeditor:
        return Error("PoEditor client is not available")

    # Begin step container
    ctx.textual.begin_step("Upload Terms to PoEditor")

    # Get required data from context
    selected_project_id = ctx.get("selected_project_id")
    terms_map = ctx.get("terms_map")
    translations_by_language = ctx.get("translations_by_language")
    source_language = ctx.get("source_language", "en")

    # Validate inputs
    if not selected_project_id:
        ctx.textual.error_text(msg("no_project_selected"))
        ctx.textual.text("")
        ctx.textual.dim_text("Please select a project first using select_project_step")
        ctx.textual.end_step("error")
        return Error("No project selected")

    if not terms_map:
        ctx.textual.error_text("No terms_map found in context")
        ctx.textual.text("")
        ctx.textual.dim_text("terms_map must be a dict mapping term keys to source language values")
        ctx.textual.end_step("error")
        return Error("No terms_map found in context")

    if not translations_by_language:
        ctx.textual.error_text("No translations_by_language found in context")
        ctx.textual.text("")
        ctx.textual.dim_text("translations_by_language must be a dict mapping language codes to translations")
        ctx.textual.end_step("error")
        return Error("No translations_by_language found in context")

    # Display upload summary
    ctx.textual.text(f"Project ID: {selected_project_id}")
    ctx.textual.text(f"Source Language: {source_language}")
    ctx.textual.text(f"Terms to upload: {len(terms_map)}")
    ctx.textual.text(f"Target languages: {len(translations_by_language)}")
    ctx.textual.text("")

    # Show sample data for debugging
    ctx.textual.dim_text("Sample terms:")
    for i, (key, value) in enumerate(list(terms_map.items())[:3]):
        ctx.textual.dim_text(f"  {key}: {value}")
        if i >= 2:
            break
    if len(terms_map) > 3:
        ctx.textual.dim_text(f"  ... and {len(terms_map) - 3} more")

    ctx.textual.text("")
    ctx.textual.dim_text("Languages:")
    for lang_code in sorted(translations_by_language.keys()):
        term_count = len(translations_by_language[lang_code])
        ctx.textual.dim_text(f"  {lang_code}: {term_count} translations")

    ctx.textual.text("")
    ctx.textual.text("Uploading to PoEditor...")

    # Upload terms and translations
    result = ctx.poeditor.create_terms_with_translations(
        project_id=selected_project_id,
        terms_map=terms_map,
        translations_by_language=translations_by_language,
        source_language=source_language
    )

    match result:
        case ClientSuccess(data=upload_result):
            ctx.textual.text("")
            ctx.textual.success_text(
                f"✓ Successfully uploaded {upload_result.terms_added} terms"
            )
            ctx.textual.success_text(
                f"✓ Updated {upload_result.languages_updated} languages"
            )

            # Show uploaded keys
            ctx.textual.text("")
            ctx.textual.dim_text("Uploaded keys:")
            for key in sorted(terms_map.keys())[:10]:
                ctx.textual.dim_text(f"  • {key}")
            if len(terms_map) > 10:
                ctx.textual.dim_text(f"  ... and {len(terms_map) - 10} more")

            ctx.textual.end_step("success")
            return Success(
                f"Uploaded {upload_result.terms_added} terms to PoEditor",
                metadata={
                    "terms_added": upload_result.terms_added,
                    "languages_updated": upload_result.languages_updated,
                    "uploaded_keys": list(terms_map.keys())
                }
            )

        case ClientError(error_message=err, error_code=code):
            ctx.textual.text("")
            ctx.textual.error_text(f"✗ Upload failed: {err}")
            if code:
                ctx.textual.dim_text(f"Error code: {code}")
            ctx.textual.end_step("error")
            return Error(f"Upload failed: {err}")


__all__ = ["upload_terms_step"]
