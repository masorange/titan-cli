"""
Compose Operations

Pure business logic for resolving which compose services a step should
operate on. These functions can be used by any step and are easily testable.
"""
from typing import Dict, List, Optional

from ..exceptions import DockerServiceGroupNotFoundError


def resolve_services(
    service_groups: Dict[str, List[str]],
    group: Optional[str] = None,
    explicit_services: Optional[List[str]] = None,
) -> List[str]:
    """
    Resolve the list of compose service names to operate on.

    Resolution order:
        1. `explicit_services`, if given, is used as-is (verbatim, no group lookup).
        2. `group`, if given, is looked up in `service_groups`.
        3. Otherwise, an empty list is returned, meaning "all services".

    Args:
        service_groups: Project-configured named groups (DockerPluginConfig.service_groups)
        group: Optional group name to resolve from `service_groups`
        explicit_services: Optional explicit list of service names, takes precedence over `group`

    Returns:
        List of service names to operate on (empty list means "all services")

    Raises:
        DockerServiceGroupNotFoundError: If `group` is given but not defined in `service_groups`
    """
    if explicit_services:
        return list(explicit_services)

    if group:
        if group not in service_groups:
            raise DockerServiceGroupNotFoundError(
                f"Service group '{group}' is not defined in the project configuration."
            )
        return list(service_groups[group])

    return []


def list_group_names(service_groups: Dict[str, List[str]]) -> List[str]:
    """
    List the names of configured service groups, in insertion order.

    Args:
        service_groups: Project-configured named groups (DockerPluginConfig.service_groups)

    Returns:
        List of group names
    """
    return list(service_groups.keys())
