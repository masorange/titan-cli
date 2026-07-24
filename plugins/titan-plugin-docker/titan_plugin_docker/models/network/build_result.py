"""Network model for a Docker build - faithful to `docker buildx build` invocation/output."""
from dataclasses import dataclass


@dataclass
class NetworkBuildResult:
    """
    Network model for a build result - raw data from the buildx invocation.
    """
    name: str
    image: str
    tag: str
    platforms: str
    target: str = ""
    pushed: bool = False
