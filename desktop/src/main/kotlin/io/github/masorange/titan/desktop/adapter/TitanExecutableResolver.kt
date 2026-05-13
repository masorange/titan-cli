package io.github.masorange.titan.desktop.adapter

import java.nio.file.Path
import kotlin.io.path.absolute
import kotlin.io.path.exists

data class TitanLaunchConfig(
    val command: List<String>,
    val projectRoot: Path,
    val workflowName: String = "headless-v1-demo",
)

class TitanExecutableResolver(
    private val environment: Map<String, String> = System.getenv(),
    private val workingDirectory: Path = Path.of(System.getProperty("user.dir")),
) {
    fun resolve(): TitanLaunchConfig {
        val command = environment["TITAN_CLI_COMMAND"]
            ?.trim()
            ?.takeIf { it.isNotEmpty() }
            ?.split(Regex("\\s+"))
            ?: listOf("poetry", "run", "titan")

        val projectRoot = environment["TITAN_PROJECT_ROOT"]
            ?.trim()
            ?.takeIf { it.isNotEmpty() }
            ?.let { Path.of(it) }
            ?: inferProjectRoot(workingDirectory)

        return TitanLaunchConfig(
            command = command,
            projectRoot = projectRoot.normalize().toAbsolutePath(),
        )
    }

    private fun inferProjectRoot(currentWorkingDirectory: Path): Path {
        val normalized = currentWorkingDirectory.toAbsolutePath().normalize()
        val parent = normalized.parent
        if (normalized.fileName?.toString() == "desktop" && parent != null) {
            return parent
        }
        if (normalized.resolve("pyproject.toml").exists()) {
            return normalized
        }
        return parent?.absolute()?.normalize() ?: normalized
    }
}
