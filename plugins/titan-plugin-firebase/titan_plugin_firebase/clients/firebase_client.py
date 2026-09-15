"""Public client facade for the Firebase plugin."""

from __future__ import annotations

from typing import Optional

from titan_cli.core.result import ClientResult

from ..config import FirebasePluginConfig
from ..models.view import UIAdcIdentity, UIRemoteConfigTemplate
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
