"""User-facing messages for the PoEditor plugin."""


def msg(key: str, **kwargs) -> str:
    """Get a user-facing message by key with optional formatting.

    Args:
        key: Message key
        **kwargs: Format arguments

    Returns:
        Formatted message string
    """
    messages = {
        "no_client": "PoEditor client not available. Please configure the plugin.",
        "no_projects": "No PoEditor projects found.",
        "invalid_project_id": "Invalid project ID: {project_id}",
        "upload_success": "Successfully uploaded {added} new terms, updated {updated}, deleted {deleted}",
        "upload_failed": "Failed to upload translations: {error}",
        "project_not_found": "Project not found: {name}",
        "list_projects_success": "Retrieved {count} projects",
        "select_project_prompt": "Select a PoEditor project:",
        "file_not_found": "Translation file not found: {file_path}",
        "invalid_language_code": "Invalid language code: {language_code}",
    }
    return messages.get(key, key).format(**kwargs)
