"""Pure business logic operations for translation and AI-powered key generation.

Operations are pure functions with no side effects.
They handle AI-powered key generation and translation workflows.
"""

import json
import re
from typing import Any

from titan_cli.core.result import ClientError, ClientSuccess


def parse_text_values(text_input: str) -> list[str]:
    """Parse text input into individual values.

    Args:
        text_input: Multi-line text with values separated by newlines

    Returns:
        List of non-empty text values
    """
    values = [line.strip() for line in text_input.split("\n") if line.strip()]
    return values


def generate_keys_with_ai(
    text_values: list[str],
    ai_client: Any,
    context: str = ""
) -> ClientSuccess[dict[str, str]] | ClientError:
    """Generate semantic keys for text values using AI.

    Args:
        text_values: List of text values to generate keys for
        ai_client: AI client from Titan workflow context
        context: Optional context about the purpose of these strings

    Returns:
        ClientResult with dict mapping generated keys to original values
    """
    if not text_values:
        return ClientError(error_message="No text values provided")

    if not ai_client:
        return ClientError(error_message="AI client not available in workflow context")

    context_note = f"\n\nContext provided by user: {context}" if context else ""

    prompt = f"""Generate keys for the following text values following the eCare PoEditor naming convention.

KEY FORMAT STRUCTURE:
<context>_<element>_<type>[_<variant>][_<platform>][_<plurals>]

COMPONENT DEFINITIONS:
1. context (REQUIRED): Screen and section where the text appears
   - Use "general" for common texts (Accept, Cancel, etc.)
   - Otherwise use: <screen>_<section>
     * screen: Name of the screen (home, invoices, settings, profile, etc.)
     * section: Section within the screen (header, list, footer, form, etc.)

2. element (REQUIRED): What the text represents or action it performs
   - Examples: purchase, unlimited_data, download_invoice, show_more, title

3. type (REQUIRED): Visual component type
   - Common types: button, text, placeholder, label, title, description, error, message

4. variant (OPTIONAL): Text variant to show
   - Examples: portrait, landscape, phone, tablet, 1, 2, 3 (for enumeration)
   - Use when multiple versions of the same text exist

5. platform (OPTIONAL): Only if platform-specific
   - Values: android, ios, web

6. plurals (OPTIONAL): Only for plural forms
   - Values: zero, one, two, few, many, other

EXAMPLES:
- "Invoices" (general navigation) → general_invoices_text
- "Download invoice" (button in invoices header) → invoices_header_download_invoice_button
- "Show more" (text in invoices list) → invoices_list_show_more_text
- "Due date" (text in invoices header) → invoices_header_due_date_text
- "Accept" (general button) → general_accept_button
- "Welcome" (title in home screen) → home_header_welcome_title

Text values to generate keys for:
{chr(10).join(f'{i+1}. "{value}"' for i, value in enumerate(text_values))}{context_note}

Return ONLY a JSON object mapping each text value to its generated key following the format above.
Format:
{{
  "text value 1": "context_element_type",
  "text value 2": "context_element_type_variant"
}}

Do not include any explanation, just the JSON object."""

    try:
        from titan_cli.ai.models import AIMessage

        messages = [AIMessage(role="user", content=prompt)]
        response = ai_client.generate(messages, max_tokens=2000)

        if not response or not response.content:
            return ClientError(error_message="AI returned empty response")

        response_text = response.content

        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON object without code blocks
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                return ClientError(error_message=f"Could not parse JSON from AI response: {response_text}")

        keys_map = json.loads(json_str)

        # Validate that we got keys for all values
        missing_values = [v for v in text_values if v not in keys_map]
        if missing_values:
            return ClientError(
                error_message=f"AI did not generate keys for all values. Missing: {missing_values}"
            )

        # Validate that all generated keys are unique
        generated_keys = list(keys_map.values())
        if len(generated_keys) != len(set(generated_keys)):
            duplicates = {k for k in generated_keys if generated_keys.count(k) > 1}
            return ClientError(
                error_message=f"AI generated duplicate keys: {duplicates}"
            )

        # Invert the map to key -> value
        result = {key: value for value, key in keys_map.items()}

        return ClientSuccess(data=result)

    except json.JSONDecodeError as e:
        return ClientError(error_message=f"Failed to parse AI response as JSON: {str(e)}")
    except Exception as e:
        return ClientError(error_message=f"Error generating keys with AI: {str(e)}")


def translate_terms_with_ai(
    terms_map: dict[str, str],
    target_languages: list[str],
    ai_client: Any,
    source_language: str = "en"
) -> ClientSuccess[dict[str, dict[str, str]]] | ClientError:
    """Translate terms to multiple languages using AI.

    Args:
        terms_map: Dict mapping keys to source language values
        target_languages: List of language codes to translate to (e.g., ["es", "fr", "de"])
        ai_client: AI client from Titan workflow context
        source_language: Source language code (default: "en")

    Returns:
        ClientResult with dict mapping language codes to {key: translation} dicts
    """
    if not terms_map:
        return ClientError(error_message="No terms provided for translation")

    if not target_languages:
        return ClientError(error_message="No target languages specified")

    if not ai_client:
        return ClientError(error_message="AI client not available in workflow context")

    translations_by_language = {}

    for language_code in target_languages:
        # Skip source language
        if language_code == source_language:
            translations_by_language[language_code] = terms_map.copy()
            continue

        prompt = f"""Translate the following mobile app strings from {source_language} to {language_code}.

Rules:
1. Maintain the same tone and context as the original
2. Use appropriate mobile app terminology for {language_code}
3. Keep formatting characters like %s, %d, {{variable}} unchanged
4. Return ONLY a JSON object mapping each key to its translation

Terms to translate:
{chr(10).join(f'{key}: "{value}"' for key, value in terms_map.items())}

Return format:
{{
  "key1": "translation1",
  "key2": "translation2"
}}

Do not include any explanation, just the JSON object."""

        try:
            from titan_cli.ai.models import AIMessage

            messages = [AIMessage(role="user", content=prompt)]
            response = ai_client.generate(messages, max_tokens=3000)

            if not response or not response.content:
                return ClientError(error_message=f"AI returned empty response for language {language_code}")

            response_text = response.content

            # Extract JSON from response
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    return ClientError(
                        error_message=f"Could not parse JSON from AI response for {language_code}: {response_text}"
                    )

            translations = json.loads(json_str)

            # Validate that we got translations for all keys
            missing_keys = [k for k in terms_map.keys() if k not in translations]
            if missing_keys:
                return ClientError(
                    error_message=f"AI did not translate all keys for {language_code}. "
                    f"Missing: {missing_keys}"
                )

            translations_by_language[language_code] = translations

        except json.JSONDecodeError as e:
            return ClientError(
                error_message=f"Failed to parse AI response as JSON for {language_code}: {str(e)}"
            )
        except Exception as e:
            return ClientError(error_message=f"Error translating to {language_code}: {str(e)}")

    return ClientSuccess(data=translations_by_language)


__all__ = [
    "parse_text_values",
    "generate_keys_with_ai",
    "translate_terms_with_ai",
]
