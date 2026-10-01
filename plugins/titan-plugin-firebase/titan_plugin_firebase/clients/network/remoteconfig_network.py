"""
HTTP executor for the Firebase Remote Config REST API.

Remote Config has no per-parameter write endpoint: a publish replaces the
whole template, guarded by an ETag. This layer only speaks HTTP — building the
modified template is `operations/`' job.
"""

from __future__ import annotations

import re
import time
from typing import Any, Optional, Sequence
from urllib.parse import urlencode

from titan_cli.core.interrupt import run_interruptible
from titan_cli.core.logging import get_logger

from ...exceptions import FirebaseApiError
from ...models.network.rest import (
    NetworkFirebaseProject,
    NetworkFirebaseProjectsPage,
    NetworkRemoteConfigTemplate,
)
from .adc_auth import AdcSession, create_adc_session

logger = get_logger(__name__)

# Google Cloud project IDs: 6-30 chars, lowercase letters, digits and hyphens,
# starting with a letter and not ending with one.
PROJECT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
FIREBASE_MANAGEMENT_BASE_URL = "https://firebase.googleapis.com/v1beta1"


class RemoteConfigNetwork:
    """Low-level GET/PUT executor for one Remote Config API base URL."""

    def __init__(
        self,
        *,
        api_base_url: str,
        request_timeout: int = 30,
        scopes: Optional[Sequence[str]] = None,
        quota_project_id: Optional[str] = None,
        management_base_url: str = FIREBASE_MANAGEMENT_BASE_URL,
        adc_session: Optional[AdcSession] = None,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.management_base_url = management_base_url.rstrip("/")
        self.request_timeout = request_timeout
        self.scopes = tuple(scopes) if scopes else None
        self.quota_project_id = quota_project_id
        self._adc_session = adc_session

    @property
    def adc_session(self) -> AdcSession:
        """Resolve ADC on first use, never during plugin initialization."""
        if self._adc_session is None:
            self._adc_session = create_adc_session(
                self.scopes,
                quota_project_id=self.quota_project_id,
            )
        return self._adc_session

    def normalize_project_id(self, project_id: str) -> str:
        """Validate a project ID before it reaches a URL."""
        normalized = project_id.strip() if project_id else ""
        if not normalized:
            raise FirebaseApiError("Firebase project_id es obligatorio.")
        if not PROJECT_ID_PATTERN.fullmatch(normalized):
            raise FirebaseApiError(
                f"'{normalized}' no es un project ID de Google Cloud válido "
                "(6-30 caracteres, minúsculas, dígitos o guiones, empieza por "
                "letra y no termina en guión)."
            )
        return normalized

    def _template_url(self, project_id: str) -> str:
        return f"{self.api_base_url}/projects/{project_id}/remoteConfig"

    def _management_projects_url(self, page_token: Optional[str] = None) -> str:
        params = {"pageSize": "100"}
        if page_token:
            params["pageToken"] = page_token
        return f"{self.management_base_url}/projects?{urlencode(params)}"

    def _headers(self, project_id: str) -> dict[str, str]:
        # Accept-Encoding is not an optimization here: the API docs require it
        # on every request. Authorization is set by AuthorizedSession.
        #
        # x-goog-user-project decides which project is billed for quota. It is
        # only set here when the credential has no quota project of its own,
        # because google.auth overwrites this header with the credential's
        # value on every request — which is why a configured quota_project_id
        # is applied to the credential in adc_auth.resolve_credentials instead.
        headers = {"Accept-Encoding": "gzip"}
        if not self._credential_quota_project():
            headers["x-goog-user-project"] = self.quota_project_id or project_id
        return headers

    def _management_headers(self) -> dict[str, str]:
        """Headers for Firebase Management calls that have no target project."""
        headers = {"Accept-Encoding": "gzip"}
        if self.quota_project_id and not self._credential_quota_project():
            headers["x-goog-user-project"] = self.quota_project_id
        return headers

    def _credential_quota_project(self) -> Optional[str]:
        """Quota project the credential will inject, if any."""
        session = self.adc_session.session
        credentials = getattr(session, "credentials", None)
        return getattr(credentials, "quota_project_id", None)

    def get_template(
        self,
        project_id: str,
    ) -> tuple[NetworkRemoteConfigTemplate, Optional[str]]:
        """
        Read the active template.

        Returns:
            The parsed template and the ETag needed to publish over it.
        """
        normalized = self.normalize_project_id(project_id)
        url = self._template_url(normalized)
        session = self.adc_session.session
        started = time.monotonic()

        response = self._request(
            lambda: session.get(
                url,
                headers=self._headers(normalized),
                timeout=self.request_timeout,
            ),
            project_id=normalized,
        )
        duration_ms = int((time.monotonic() - started) * 1000)

        if response.status_code != 200:
            raise self._api_error(response, normalized, operation="lectura")

        template = self._parse_template(response)
        etag = response.headers.get("ETag")
        logger.debug(
            "firebase_remoteconfig_get_ok",
            project_id=normalized,
            etag=etag,
            parameter_count=len(template.parameters),
            condition_count=len(template.conditions),
            duration_ms=duration_ms,
        )
        return template, etag

    def list_projects(self) -> list[NetworkFirebaseProject]:
        """
        List Firebase projects the active credentials can access.

        The Firebase Management API returns only Firebase projects, unlike
        Cloud Resource Manager which lists generic Google Cloud projects.
        """
        session = self.adc_session.session
        projects: list[NetworkFirebaseProject] = []
        page_token: Optional[str] = None

        while True:
            url = self._management_projects_url(page_token)
            started = time.monotonic()
            response = self._request(
                lambda: session.get(
                    url,
                    headers=self._management_headers(),
                    timeout=self.request_timeout,
                ),
                project_id="firebase-projects",
            )
            duration_ms = int((time.monotonic() - started) * 1000)

            if response.status_code != 200:
                raise self._management_api_error(response, operation="listado")

            page = self._parse_projects_page(response)
            projects.extend(page.results)
            logger.debug(
                "firebase_projects_list_page_ok",
                project_count=len(page.results),
                has_next_page=bool(page.next_page_token),
                duration_ms=duration_ms,
            )
            if not page.next_page_token:
                break
            page_token = page.next_page_token

        return sorted(projects, key=lambda project: project.project_id)

    def put_template(
        self,
        project_id: str,
        payload: dict[str, Any],
        *,
        etag: str,
        validate_only: bool = False,
    ) -> tuple[NetworkRemoteConfigTemplate, Optional[str]]:
        """
        Publish (or validate) a whole template.

        Args:
            payload: The complete template JSON. Anything missing from it is
                deleted from the project.
            etag: The ETag from the read this payload was built on. Sent as
                `If-Match`, which is what makes a concurrent console edit fail
                loudly instead of being overwritten. Never `*`.
            validate_only: Ask Firebase to check the payload without publishing.
        """
        normalized = self.normalize_project_id(project_id)
        if not etag or not etag.strip():
            raise FirebaseApiError(
                "Falta el ETag de la lectura previa. Publicar sin If-Match "
                "pisaría los cambios de quien esté editando la consola."
            )

        url = self._template_url(normalized)
        if validate_only:
            url = f"{url}?validate_only=true"

        headers = self._headers(normalized)
        headers["Content-Type"] = "application/json; UTF8"
        headers["If-Match"] = etag.strip()

        session = self.adc_session.session
        started = time.monotonic()
        response = self._request(
            lambda: session.put(
                url,
                json=payload,
                headers=headers,
                timeout=self.request_timeout,
            ),
            project_id=normalized,
        )
        duration_ms = int((time.monotonic() - started) * 1000)

        if response.status_code != 200:
            raise self._api_error(
                response,
                normalized,
                operation="validación" if validate_only else "publicación",
            )

        template = self._parse_template(response)
        new_etag = response.headers.get("ETag")
        logger.debug(
            "firebase_remoteconfig_put_ok",
            project_id=normalized,
            validate_only=validate_only,
            etag=new_etag,
            version_number=(
                template.version.version_number if template.version else None
            ),
            duration_ms=duration_ms,
        )
        return template, new_etag

    def _request(self, call, *, project_id: str):
        """Run one HTTP call so app exit can abandon it."""
        import requests

        try:
            # A publish abandoned on app exit is safe: the If-Match guard means
            # Firebase either applied the whole template or none of it.
            return run_interruptible(call)
        except requests.RequestException as exc:
            logger.debug(
                "firebase_remoteconfig_request_failed",
                project_id=project_id,
                error=str(exc),
            )
            raise FirebaseApiError(
                f"La petición a Firebase Remote Config falló: {exc}"
            ) from exc

    @staticmethod
    def _parse_template(response) -> NetworkRemoteConfigTemplate:
        """Parse a template payload, rejecting anything that is not an object."""
        try:
            payload = response.json()
        except ValueError as exc:
            raise FirebaseApiError(
                "La respuesta de Firebase Remote Config no era JSON válido."
            ) from exc
        if not isinstance(payload, dict):
            raise FirebaseApiError(
                "La respuesta de Firebase Remote Config no era un objeto JSON."
            )
        return NetworkRemoteConfigTemplate.model_validate(payload)

    @staticmethod
    def _parse_projects_page(response) -> NetworkFirebaseProjectsPage:
        """Parse a Firebase Management projects list page."""
        try:
            payload = response.json()
        except ValueError as exc:
            raise FirebaseApiError(
                "La respuesta de Firebase Management no era JSON valido."
            ) from exc
        if not isinstance(payload, dict):
            raise FirebaseApiError(
                "La respuesta de Firebase Management no era un objeto JSON."
            )
        return NetworkFirebaseProjectsPage.model_validate(payload)

    def _api_error(
        self,
        response,
        project_id: str,
        *,
        operation: str,
    ) -> FirebaseApiError:
        """Turn a failed response into an error a user can act on."""
        detail = self._extract_error_detail(response)
        status = response.status_code
        quota_project = self.quota_project_id or project_id

        if status == 401:
            message = (
                "Firebase rechazó las credenciales (ADC). Vuelve a ejecutar: "
                "gcloud auth application-default login"
            )
        elif status == 403:
            message = (
                f"Permiso denegado en la {operation} de Remote Config para "
                f"'{project_id}'. Necesitas acceso a Remote Config en ese "
                f"proyecto y permiso serviceusage.services.use en el proyecto "
                f"de cuota '{quota_project}'"
            )
        elif status == 404:
            message = (
                f"No existe el proyecto o la plantilla de Remote Config de "
                f"'{project_id}'"
            )
        elif status == 409:
            message = (
                "La plantilla cambió en Firebase desde la lectura (ETag "
                "caducado). Hay que volver a leerla y reaplicar el cambio"
            )
        elif status == 400:
            message = (
                f"Firebase rechazó la {operation} de la plantilla. Un 400 "
                "también significa ETag caducado o ausente"
            )
        else:
            message = f"La {operation} de Remote Config falló con estado {status}"

        logger.debug(
            "firebase_remoteconfig_api_error",
            project_id=project_id,
            status_code=status,
            operation=operation,
        )
        return FirebaseApiError(
            f"{message}. {detail}",
            status_code=status,
            detail=detail,
        )

    def _management_api_error(
        self,
        response,
        *,
        operation: str,
    ) -> FirebaseApiError:
        """Turn a failed Firebase Management response into an actionable error."""
        detail = self._extract_error_detail(response)
        status = response.status_code

        if status == 401:
            message = (
                "Firebase rechazó las credenciales (ADC). Vuelve a ejecutar: "
                "gcloud auth application-default login"
            )
        elif status == 403:
            message = (
                "Permiso denegado en el listado de proyectos Firebase. "
                "Necesitas acceso para listar Firebase projects con estas ADC"
            )
        else:
            message = f"El {operation} de proyectos Firebase falló con estado {status}"

        logger.debug(
            "firebase_management_api_error",
            status_code=status,
            operation=operation,
        )
        return FirebaseApiError(
            f"{message}. {detail}",
            status_code=status,
            detail=detail,
        )

    @staticmethod
    def _extract_error_detail(response) -> str:
        """Extract a concise detail from a Google API error payload."""
        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message")
                if message:
                    return str(message)
            if error:
                return str(error)

        text = (getattr(response, "text", "") or "").strip()
        return text or "Sin detalle en la respuesta."
