package io.github.masorange.titan.desktop.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.Button
import androidx.compose.material.Card
import androidx.compose.material.MaterialTheme
import androidx.compose.material.OutlinedButton
import androidx.compose.material.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp

@Composable
fun WorkflowScreen(
    statusText: String,
    projectRoot: String,
    commandPreview: String,
    workflowName: String,
    protocolEvents: List<String>,
    diagnostics: List<String>,
    isRunActive: Boolean,
    onStart: () -> Unit,
    onCancel: () -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        horizontalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Column(
            modifier = Modifier.weight(0.38f).fillMaxHeight(),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            SectionCard(title = "Run Header") {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Workflow: $workflowName", style = MaterialTheme.typography.h6)
                    Text("Status: $statusText")
                    Text("Project path: $projectRoot")
                    Text("Titan command: $commandPreview")
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = onStart, enabled = !isRunActive) {
                            Text("Start")
                        }
                        OutlinedButton(onClick = onCancel, enabled = isRunActive) {
                            Text("Cancel")
                        }
                    }
                }
            }

            SectionCard(title = "Step List") {
                PlaceholderBlock(
                    "P2-001 only leaves the screen shell ready. The derived step state model will be implemented in P2-002.",
                )
            }

            SectionCard(title = "Active Prompt") {
                PlaceholderBlock(
                    "Prompt rendering and submit interaction will be connected after the event stream drives desktop state.",
                )
            }
        }

        Column(
            modifier = Modifier.weight(0.62f).fillMaxHeight(),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            SectionCard(title = "Output Timeline / Raw Event Stream", modifier = Modifier.weight(1f)) {
                LogPanel(lines = protocolEvents, emptyMessage = "No protocol events captured yet.")
            }

            SectionCard(title = "Diagnostics (stderr)", modifier = Modifier.height(220.dp)) {
                LogPanel(lines = diagnostics, emptyMessage = "No diagnostics yet.")
            }
        }
    }
}

@Composable
private fun SectionCard(
    title: String,
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Card(modifier = modifier.fillMaxWidth(), elevation = 6.dp) {
        Column(
            modifier = Modifier.fillMaxSize().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(title, style = MaterialTheme.typography.h6)
            content()
        }
    }
}

@Composable
private fun PlaceholderBlock(message: String) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color(0xFFF4F4F4))
            .padding(12.dp),
    ) {
        Text(message)
    }
}

@Composable
private fun LogPanel(lines: List<String>, emptyMessage: String) {
    if (lines.isEmpty()) {
        PlaceholderBlock(emptyMessage)
        return
    }

    SelectionContainer {
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .background(Color(0xFF101418))
                .padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            items(lines) { line ->
                Text(
                    text = line,
                    color = Color(0xFFE6EDF3),
                    fontFamily = FontFamily.Monospace,
                )
            }
        }
    }
}
