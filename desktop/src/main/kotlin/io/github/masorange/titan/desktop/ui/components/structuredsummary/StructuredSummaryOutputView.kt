package io.github.masorange.titan.desktop.ui.components.structuredsummary

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.Card
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.material.MaterialTheme
import androidx.compose.material.Text
import androidx.compose.ui.graphics.Color
import io.github.masorange.titan.desktop.state.OutputItemState
import io.github.masorange.titan.desktop.state.OutputVisualFormat
import io.github.masorange.titan.desktop.theme.H3Text
import io.github.masorange.titan.desktop.theme.H4Text
import io.github.masorange.titan.desktop.theme.spacings.Spacing
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import kotlinx.serialization.json.add
import kotlinx.serialization.json.addJsonObject
import org.jetbrains.compose.ui.tooling.preview.Preview

@Composable
fun StructuredSummaryOutputView(item: OutputItemState) {
    val summaryLines = item.metadata.summaryLines().ifEmpty {
        item.content.lines().filter { it.isNotBlank() }
    }
    val sections = item.metadata.summarySections()
    val title = item.title

    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {

        title?.let {
            H3Text(text = title)
        }

        summaryLines.forEach { line ->
            H4Text(text = line)
        }

        sections.forEach { section ->
            Text(section.title, style = MaterialTheme.typography.subtitle1)
            section.lines.forEach { line ->
                Text(line, style = MaterialTheme.typography.body2)
            }
        }
    }
}

private data class StructuredSummarySection(
    val title: String,
    val lines: List<String>,
)

private fun JsonObject.summaryLines(): List<String> =
    this["summary_lines"]
        ?.asJsonArrayOrNull()
        ?.mapNotNull { it.asStringOrNull() }
        ?: emptyList()

private fun JsonObject.summarySections(): List<StructuredSummarySection> =
    this["sections"]
        ?.asJsonArrayOrNull()
        ?.mapNotNull { element ->
            val section = element as? JsonObject ?: return@mapNotNull null
            val title = section["title"]?.asStringOrNull()?.takeIf { it.isNotBlank() } ?: return@mapNotNull null
            StructuredSummarySection(
                title = title,
                lines = section["lines"]
                    ?.asJsonArrayOrNull()
                    ?.mapNotNull { it.asStringOrNull() }
                    ?: emptyList(),
            )
        }
        ?: emptyList()

private fun JsonElement.asStringOrNull(): String? = runCatching { jsonPrimitive.content }.getOrNull()

private fun JsonElement.asJsonArrayOrNull(): JsonArray? = runCatching { jsonArray }.getOrNull()


@Preview
@Composable
private fun WorkflowScreenPreview() {
    MaterialTheme {
        Card(modifier = Modifier.background(Color.White).padding(Spacing.s6), elevation = 0.dp) {
            StructuredSummaryOutputView(
                item = OutputItemState(
                    sequence = 1,
                    stepId = "classify_pr",
                    stepName = "Classify PR",
                    format = OutputVisualFormat.STRUCTURED_SUMMARY,
                    title = "PR Classification",
                    content = "Size class: MEDIUM\nFiles changed: 12",
                    metadata = buildJsonObject {
                        put("kind", "pr_classification")
                        putJsonArray("summary_lines") {
                            add(JsonPrimitive("Size class: MEDIUM"))
                            add(JsonPrimitive("Files changed: 12"))
                            add(JsonPrimitive("Lines changed: 184"))
                        }
                        putJsonArray("sections") {
                            addJsonObject {
                                put("title", "Scope")
                                putJsonArray("lines") {
                                    add(JsonPrimitive("Files changed: 12"))
                                    add(JsonPrimitive("Lines changed: 184"))
                                }
                            }
                            addJsonObject {
                                put("title", "Flags")
                                putJsonArray("lines") {
                                    add(JsonPrimitive("Active review: yes"))
                                    add(JsonPrimitive("Repetitive migration: no"))
                                }
                            }
                        }
                    },
                )
            )
        }
    }
}
