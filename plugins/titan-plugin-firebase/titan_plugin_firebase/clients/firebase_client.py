"""Public client facade for the Firebase plugin."""

from __future__ import annotations

from typing import Optional

from titan_cli.core.result import ClientResult

from ..config import FirebasePluginConfig
from ..models.view import (
    UIAdcIdentity,
    UIRemoteConfigChangeSet,
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
        conditions: Optional[list] = None,
    ) -> ClientResult[UIRemoteConfigChangeSet]:
        """
        Check one parameter edit against the live template.

        Validates that the parameter and every condition exist and that the
        value matches the parameter's type, and reports the value each target
        would replace. `conditions` holds one entry per target, where None
        means the parameter's default value. Nothing is published.
        """
        return self._remote_config.validate_change_set(
            project_id,
            key,
            new_value,
            conditions,
        )

    def publish_remote_config_change(
        self,
        project_id: str,
        change_set: UIRemoteConfigChangeSet,
        *,
        validate_only: bool = False,
    ) -> ClientResult[UIRemoteConfigPublishResult]:
        """
        Apply a change set to the template and publish it.

        Reads the template, replaces the value of every target in the set, and
        publishes the whole template under the ETag of that read — retrying
        once if someone published in between. Every target lands in the same
        publish, so it is one Remote Config version regardless of how many
        targets there are. With `validate_only` Firebase checks the payload and
        publishes nothing.
        """
        return self._remote_config.publish_change_set(
            project_id,
            change_set,
            validate_only=validate_only,
        )
