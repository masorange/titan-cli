"""Public client facade for the Firebase plugin."""

from __future__ import annotations

from typing import Optional

from titan_cli.core.result import ClientResult

from ..config import FirebasePluginConfig
from ..models.view import (
    UIAdcIdentity,
    UIFirebaseProject,
    UIRemoteConfigChange,
    UIRemoteConfigKeyCopyResult,
    UIRemoteConfigKeyCreateRequest,
    UIRemoteConfigKeyCreateResult,
    UIRemoteConfigPublishResult,
    UIRemoteConfigTemplate,
)
from .network.remoteconfig_network import RemoteConfigNetwork
from .services.remoteconfig_service import RemoteConfigService


class FirebaseClient:
    """
    Facade steps use for Remote Config.

    Construction does no I/O: Application Default Credentials are resolved on
    the first network call, so enabling the plugin never blocks on gcloud.
    """

    def __init__(
        self,
        config: FirebasePluginConfig,
        *,
        network: Optional[RemoteConfigNetwork] = None,
    ) -> None:
        self.config = config
        self._network = network or RemoteConfigNetwork(
            api_base_url=config.api_base_url,
            request_timeout=config.request_timeout,
            scopes=config.oauth_scopes,
            quota_project_id=config.quota_project_id,
        )
        self._remote_config = RemoteConfigService(self._network)

    def check_auth(self) -> ClientResult[UIAdcIdentity]:
        """Verify ADC and report which identity will own the changes."""
        return self._remote_config.check_auth()

    def uses_service_account_env_var(self) -> bool:
        """Whether GOOGLE_APPLICATION_CREDENTIALS would decide the identity."""
        return self._remote_config.uses_service_account_env_var()

    def list_projects(self) -> ClientResult[list[UIFirebaseProject]]:
        """List Firebase projects available to the active credentials."""
        return self._remote_config.list_projects()

    def get_remote_config(
        self,
        project_id: str,
    ) -> ClientResult[UIRemoteConfigTemplate]:
        """Read the active Remote Config template for one project."""
        return self._remote_config.get_template(project_id)

    def validate_remote_config_change(
        self,
        project_id: str,
        key: str,
        new_value: str,
        condition: Optional[str] = None,
    ) -> ClientResult[UIRemoteConfigChange]:
        """
        Check one parameter edit against the live template.

        Validates that the parameter and condition exist and that the value
        matches the parameter's type, and reports the value it would replace.
        Nothing is published. Values owned by Firebase personalization,
        experiments, rollouts, or unknown future value-source fields are
        rejected before they can be overwritten.
        """
        return self._remote_config.validate_change(
            project_id,
            key,
            new_value,
            condition,
        )

    def publish_remote_config_change(
        self,
        project_id: str,
        change: UIRemoteConfigChange,
        *,
        validate_only: bool = False,
    ) -> ClientResult[UIRemoteConfigPublishResult]:
        """
        Apply one parameter change to the template and publish it.

        Reads the template, replaces exactly that one value, and publishes the
        whole template under the ETag of that read — retrying once if someone
        published in between. With `validate_only` Firebase checks the payload
        and publishes nothing. The live value source is checked again before
        the publish payload is built.
        """
        return self._remote_config.publish_change(
            project_id,
            change,
            validate_only=validate_only,
        )

    def copy_remote_config_key(
        self,
        source_project_id: str,
        target_project_id: str,
        key: str,
        *,
        validate_only: bool = False,
    ) -> ClientResult[UIRemoteConfigKeyCopyResult]:
        """
        Copy a missing Remote Config parameter from one project to another.

        The target template is validated or published with the same ETag
        guarded read-modify-write path as normal value edits. Existing target
        parameters are never overwritten, and Firebase-managed source values
        are not copied by this generic method.
        """
        return self._remote_config.copy_key(
            source_project_id,
            target_project_id,
            key,
            validate_only=validate_only,
        )

    def create_remote_config_key(
        self,
        project_id: str,
        request: UIRemoteConfigKeyCreateRequest,
        *,
        validate_only: bool = False,
    ) -> ClientResult[UIRemoteConfigKeyCreateResult]:
        """
        Create a missing Remote Config parameter in one project.

        Values are carried in `request`, which is passed through positionally
        to keep value-bearing data out of keyword-argument logs.
        """
        return self._remote_config.create_key(
            project_id,
            request,
            validate_only=validate_only,
        )
