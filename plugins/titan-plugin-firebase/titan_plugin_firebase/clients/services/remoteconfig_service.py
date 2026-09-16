"""
Remote Config data access.

Every method returns `ClientResult`, so steps never handle exceptions.

One caveat on logging: `@log_client_operation` writes every keyword argument
at DEBUG. Parameter values can carry business-sensitive content, so anything
value-bearing is passed positionally and never as a kwarg.
"""

from __future__ import annotations

from typing import Optional

from titan_cli.core.logging import log_client_operation
from titan_cli.core.result import ClientError, ClientResult, ClientSuccess

from ...exceptions import (
    FirebaseApiError,
    FirebaseAuthUnavailableError,
)
from ...models.mappers import map_project, map_template, map_version
from ...models.view import (
    UIAdcIdentity,
    UIFirebaseProject,
    UIRemoteConfigChange,
    UIRemoteConfigKeyCopyResult,
    UIRemoteConfigKeyCreateResult,
    UIRemoteConfigKeyCreateRequest,
    UIRemoteConfigPublishResult,
    UIRemoteConfigTemplate,
)
from ...operations.template_operations import (
    TemplateEditError,
    add_parameter_to_payload,
    apply_change,
    build_change,
    build_parameter_payload,
    effective_value_type_for,
    parameter_payload,
)  # build_change is the pure operation; the service method below is validate_change
from ...models.values import RemoteConfigValueError
from ..network.adc_auth import ADC_LOGIN_HINT, service_account_env_var_set
from ..network.remoteconfig_network import RemoteConfigNetwork

_STATUS_ERROR_CODES = {
    400: "BAD_REQUEST",
    401: "AUTH_REJECTED",
    403: "PERMISSION_DENIED",
    404: "NOT_FOUND",
    409: "ETAG_CONFLICT",
}


def _api_error_to_client_error(exc: FirebaseApiError) -> ClientError:
    """Map an API failure to a ClientError, keeping the actionable message."""
    status = exc.status_code
    error_code = _STATUS_ERROR_CODES.get(status or 0, "API_ERROR")
    # A stale ETag and a missing project are expected outcomes a workflow
    # recovers from; only genuine failures deserve an error-level log.
    log_level = "warning" if status in {404, 409} else "error"
    return ClientError(
        error_message=str(exc),
        error_code=error_code,
        log_level=log_level,
        details={"status_code": status} if status else None,
    )


class RemoteConfigService:
    """Reads and publishes Remote Config templates for one plugin config."""

    def __init__(self, network: RemoteConfigNetwork) -> None:
        self._network = network

    @log_client_operation("firebase_check_auth")
    def check_auth(self) -> ClientResult[UIAdcIdentity]:
        """
        Verify Application Default Credentials and report the identity.

        A service-account credential is reported, not rejected: it works, but
        every publish would be attributed to the service account instead of
        the person running the workflow.
        """
        try:
            identity = self._network.adc_session.identity
        except FirebaseAuthUnavailableError as exc:
            return ClientError(
                error_message=str(exc),
                error_code="ADC_UNAVAILABLE",
                details={"login_command": ADC_LOGIN_HINT},
            )

        message = "ADC activas con credenciales de usuario"
        if not identity.is_user_credential:
            message = (
                f"ADC activas como {identity.credential_kind} "
                f"({identity.display_account})"
            )
        return ClientSuccess(
            data=identity,
            message=message,
        )

    @log_client_operation("firebase_list_projects")
    def list_projects(self) -> ClientResult[list[UIFirebaseProject]]:
        """List Firebase projects available to the active credentials."""
        try:
            projects = self._network.list_projects()
        except FirebaseAuthUnavailableError as exc:
            return ClientError(
                error_message=str(exc),
                error_code="ADC_UNAVAILABLE",
                details={"login_command": ADC_LOGIN_HINT},
            )
        except FirebaseApiError as exc:
            return _api_error_to_client_error(exc)

        ui_projects = [map_project(project) for project in projects]
        return ClientSuccess(
            data=ui_projects,
            message=f"{len(ui_projects)} proyectos Firebase disponibles",
        )

    @log_client_operation("firebase_get_remote_config")
    def get_template(self, project_id: str) -> ClientResult[UIRemoteConfigTemplate]:
        """Read the active Remote Config template for one project."""
        try:
            template, etag = self._network.get_template(project_id)
        except FirebaseAuthUnavailableError as exc:
            return ClientError(
                error_message=str(exc),
                error_code="ADC_UNAVAILABLE",
                details={"login_command": ADC_LOGIN_HINT},
            )
        except FirebaseApiError as exc:
            return _api_error_to_client_error(exc)

        ui_template = map_template(project_id.strip(), template, etag)
        return ClientSuccess(
            data=ui_template,
            message=(
                f"{ui_template.parameter_count} parámetros y "
                f"{len(ui_template.conditions)} condiciones en {project_id}"
            ),
        )

    def uses_service_account_env_var(self) -> bool:
        """Whether GOOGLE_APPLICATION_CREDENTIALS would decide the identity."""
        return service_account_env_var_set()

    @log_client_operation("firebase_publish_remote_config")
    def publish_change(
        self,
        project_id,
        change,
        *,
        validate_only: bool = False,
    ) -> ClientResult[UIRemoteConfigPublishResult]:
        """
        Apply one parameter change and publish (or validate) the template.

        The read happens here, immediately before the write, so the ETag is as
        fresh as it can be. A conflict means someone published between the two
        calls: the read-modify-write is retried once against the new template,
        which is the documented recovery and is safe because the change is
        described declaratively (key, target, value) rather than as a
        pre-rendered payload.

        `change` and its value are positional on purpose: the logging decorator
        records keyword arguments, and a parameter value can carry
        business-sensitive content.
        """
        attempt = self._attempt_publish(project_id, change, validate_only)
        if isinstance(attempt, ClientError) and attempt.error_code == "ETAG_CONFLICT":
            retry = self._attempt_publish(project_id, change, validate_only)
            if isinstance(retry, ClientSuccess):
                return ClientSuccess(
                    data=UIRemoteConfigPublishResult(
                        project_id=retry.data.project_id,
                        validated_only=retry.data.validated_only,
                        etag=retry.data.etag,
                        version=retry.data.version,
                        change=retry.data.change,
                        retried_after_conflict=True,
                    ),
                    message=f"{retry.message} (tras reintentar por ETag)",
                )
            return retry
        return attempt

    def _attempt_publish(
        self,
        project_id: str,
        change: UIRemoteConfigChange,
        validate_only: bool,
    ) -> ClientResult[UIRemoteConfigPublishResult]:
        """One read-modify-write cycle."""
        payload, etag, error = self.raw_template(project_id)
        if error is not None:
            return error
        if not etag:
            return ClientError(
                error_message=(
                    "Firebase no devolvió ETag en la lectura, así que no se "
                    "puede publicar sin riesgo de pisar otros cambios."
                ),
                error_code="MISSING_ETAG",
            )

        try:
            updated = apply_change(payload, change)
        except TemplateEditError as exc:
            return ClientError(
                error_message=str(exc),
                error_code="TEMPLATE_EDIT_ERROR",
                log_level="warning",
            )

        try:
            template, new_etag = self._network.put_template(
                project_id,
                updated,
                etag=etag,
                validate_only=validate_only,
            )
        except FirebaseAuthUnavailableError as exc:
            return ClientError(
                error_message=str(exc),
                error_code="ADC_UNAVAILABLE",
                details={"login_command": ADC_LOGIN_HINT},
            )
        except FirebaseApiError as exc:
            return _api_error_to_client_error(exc)

        version = map_version(template.version)
        result = UIRemoteConfigPublishResult(
            project_id=project_id.strip(),
            validated_only=validate_only,
            etag=new_etag,
            version=version,
            change=change,
        )
        message = (
            f"Plantilla validada para {project_id}"
            if validate_only
            else (
                f"Publicada la versión {result.version_number or '?'} de {project_id}"
            )
        )
        return ClientSuccess(data=result, message=message)

    @log_client_operation("firebase_validate_change")
    def validate_change(
        self,
        project_id,
        key,
        new_value,
        condition=None,
    ) -> ClientResult[UIRemoteConfigChange]:
        """
        Validate a requested edit against the live template.

        Arguments are positional because the value can be sensitive and the
        logging decorator would record it as a keyword.
        """
        payload, _etag, error = self.raw_template(project_id)
        if error is not None:
            return error

        try:
            change = build_change(payload, key, new_value, condition)
        except TemplateEditError as exc:
            return ClientError(
                error_message=str(exc),
                error_code="TEMPLATE_EDIT_ERROR",
                log_level="warning",
            )
        except RemoteConfigValueError as exc:
            return ClientError(
                error_message=str(exc),
                error_code="INVALID_VALUE",
                log_level="warning",
            )

        return ClientSuccess(
            data=change,
            message=f"Cambio validado para {key}",
        )

    @log_client_operation("firebase_copy_remote_config_key")
    def copy_key(
        self,
        source_project_id,
        target_project_id,
        key,
        *,
        validate_only: bool = False,
    ) -> ClientResult[UIRemoteConfigKeyCopyResult]:
        """
        Copy one missing Remote Config key from a source project to a target.

        The target template is still published as a whole template guarded by
        the target ETag. Existing target parameters are never overwritten.
        """
        attempt = self._attempt_copy_key(
            source_project_id,
            target_project_id,
            key,
            validate_only,
        )
        if isinstance(attempt, ClientError) and attempt.error_code == "ETAG_CONFLICT":
            retry = self._attempt_copy_key(
                source_project_id,
                target_project_id,
                key,
                validate_only,
            )
            if isinstance(retry, ClientSuccess):
                return ClientSuccess(
                    data=UIRemoteConfigKeyCopyResult(
                        source_project_id=retry.data.source_project_id,
                        project_id=retry.data.project_id,
                        key=retry.data.key,
                        value_type=retry.data.value_type,
                        validated_only=retry.data.validated_only,
                        etag=retry.data.etag,
                        version=retry.data.version,
                        retried_after_conflict=True,
                    ),
                    message=f"{retry.message} (tras reintentar por ETag)",
                )
            return retry
        return attempt

    def _attempt_copy_key(
        self,
        source_project_id: str,
        target_project_id: str,
        key: str,
        validate_only: bool,
    ) -> ClientResult[UIRemoteConfigKeyCopyResult]:
        """One source-read plus target read-modify-write cycle."""
        source_payload, _source_etag, source_error = self.raw_template(
            source_project_id
        )
        if source_error is not None:
            return source_error
        target_payload, target_etag, target_error = self.raw_template(target_project_id)
        if target_error is not None:
            return target_error
        if not target_etag:
            return ClientError(
                error_message=(
                    "Firebase no devolvió ETag en la lectura destino, así que "
                    "no se puede publicar sin riesgo de pisar otros cambios."
                ),
                error_code="MISSING_ETAG",
            )

        try:
            source_parameter = parameter_payload(source_payload, key)
            value_type = effective_value_type_for(source_payload, key)
            updated = add_parameter_to_payload(
                target_payload,
                key,
                source_parameter,
                version_description=(
                    f"Titan: copied Remote Config key {key} from {source_project_id}"
                ),
            )
        except TemplateEditError as exc:
            return ClientError(
                error_message=str(exc),
                error_code="TEMPLATE_EDIT_ERROR",
                log_level="warning",
            )

        try:
            template, new_etag = self._network.put_template(
                target_project_id,
                updated,
                etag=target_etag,
                validate_only=validate_only,
            )
        except FirebaseAuthUnavailableError as exc:
            return ClientError(
                error_message=str(exc),
                error_code="ADC_UNAVAILABLE",
                details={"login_command": ADC_LOGIN_HINT},
            )
        except FirebaseApiError as exc:
            return _api_error_to_client_error(exc)

        result = UIRemoteConfigKeyCopyResult(
            source_project_id=source_project_id.strip(),
            project_id=target_project_id.strip(),
            key=key,
            value_type=value_type,
            validated_only=validate_only,
            etag=new_etag,
            version=map_version(template.version),
        )
        action = "validada" if validate_only else "publicada"
        return ClientSuccess(
            data=result,
            message=f"Clave {key} {action} en {target_project_id}",
        )

    @log_client_operation("firebase_create_remote_config_key")
    def create_key(
        self,
        project_id,
        request: UIRemoteConfigKeyCreateRequest,
        *,
        validate_only: bool = False,
    ) -> ClientResult[UIRemoteConfigKeyCreateResult]:
        """
        Create one missing Remote Config key in a target project.

        The full template is read and published under its ETag. Existing
        target parameters are never overwritten.
        """
        attempt = self._attempt_create_key(project_id, request, validate_only)
        if isinstance(attempt, ClientError) and attempt.error_code == "ETAG_CONFLICT":
            retry = self._attempt_create_key(project_id, request, validate_only)
            if isinstance(retry, ClientSuccess):
                return ClientSuccess(
                    data=UIRemoteConfigKeyCreateResult(
                        project_id=retry.data.project_id,
                        key=retry.data.key,
                        value_type=retry.data.value_type,
                        validated_only=retry.data.validated_only,
                        etag=retry.data.etag,
                        version=retry.data.version,
                        retried_after_conflict=True,
                    ),
                    message=f"{retry.message} (tras reintentar por ETag)",
                )
            return retry
        return attempt

    def _attempt_create_key(
        self,
        project_id: str,
        request: UIRemoteConfigKeyCreateRequest,
        validate_only: bool,
    ) -> ClientResult[UIRemoteConfigKeyCreateResult]:
        """One read-modify-write cycle that adds a new parameter."""
        payload, etag, error = self.raw_template(project_id)
        if error is not None:
            return error
        if not etag:
            return ClientError(
                error_message=(
                    "Firebase no devolvió ETag en la lectura destino, así que "
                    "no se puede publicar sin riesgo de pisar otros cambios."
                ),
                error_code="MISSING_ETAG",
            )

        try:
            new_parameter = build_parameter_payload(
                request.value_type,
                request.default_raw_value,
                conditional_values=request.conditional_raw_values,
                description=request.description,
            )
            updated = add_parameter_to_payload(
                payload,
                request.key,
                new_parameter,
                version_description=f"Titan: created Remote Config key {request.key}",
            )
        except TemplateEditError as exc:
            return ClientError(
                error_message=str(exc),
                error_code="TEMPLATE_EDIT_ERROR",
                log_level="warning",
            )
        except RemoteConfigValueError as exc:
            return ClientError(
                error_message=str(exc),
                error_code="INVALID_VALUE",
                log_level="warning",
            )

        try:
            template, new_etag = self._network.put_template(
                project_id,
                updated,
                etag=etag,
                validate_only=validate_only,
            )
        except FirebaseAuthUnavailableError as exc:
            return ClientError(
                error_message=str(exc),
                error_code="ADC_UNAVAILABLE",
                details={"login_command": ADC_LOGIN_HINT},
            )
        except FirebaseApiError as exc:
            return _api_error_to_client_error(exc)

        result = UIRemoteConfigKeyCreateResult(
            project_id=project_id.strip(),
            key=request.key,
            value_type=request.value_type,
            validated_only=validate_only,
            etag=new_etag,
            version=map_version(template.version),
        )
        action = "validada" if validate_only else "publicada"
        return ClientSuccess(
            data=result,
            message=f"Clave {request.key} {action} en {project_id}",
        )

    def raw_template(
        self,
        project_id: str,
    ) -> tuple[Optional[dict], Optional[str], Optional[ClientError]]:
        """
        Read the template as the exact payload the API returned, plus its ETag.

        Publishing replaces the whole template, so a write path needs the raw
        payload — the UI model is lossy by design.
        """
        try:
            template, etag = self._network.get_template(project_id)
        except FirebaseAuthUnavailableError as exc:
            return (
                None,
                None,
                ClientError(
                    error_message=str(exc),
                    error_code="ADC_UNAVAILABLE",
                    details={"login_command": ADC_LOGIN_HINT},
                ),
            )
        except FirebaseApiError as exc:
            return None, None, _api_error_to_client_error(exc)
        return template.to_payload(), etag, None
