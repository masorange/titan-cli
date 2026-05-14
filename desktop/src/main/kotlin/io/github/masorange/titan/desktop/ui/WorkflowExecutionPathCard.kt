package io.github.masorange.titan.desktop.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.Card
import androidx.compose.material.MaterialTheme
import androidx.compose.material.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import org.jetbrains.compose.ui.tooling.preview.Preview

private val TimelineGreen = Color(0xFF10B981)
private val TimelineLine = Color(0xFFD1D5DB)
private val CardBorder = Color(0xFFE5E7EB)
private val SubtitleColor = Color(0xFF4B5563)
private val DurationColor = Color(0xFF374151)

@Composable
fun WorkflowExecutionPathCard(
    title: String,
    subtitle: String,
    duration: String? = null,
    modifier: Modifier = Modifier,
    isLast: Boolean = false,
    indicatorText: String = "✓",
    indicatorColor: Color = TimelineGreen,
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(14.dp),
        verticalAlignment = Alignment.Top,
    ) {
        TimelineMarker(
            isLast = isLast,
            indicatorText = indicatorText,
            indicatorColor = indicatorColor,
        )

        Card(
            modifier = Modifier
                .weight(1f)
                .border(width = 1.dp, color = CardBorder, shape = MaterialTheme.shapes.medium),
            elevation = 0.dp,
            shape = MaterialTheme.shapes.medium,
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp, vertical = 18.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.Top,
                ) {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.h6.copy(fontWeight = FontWeight.Medium),
                        modifier = Modifier.weight(1f),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )

                    if (duration != null) {
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(
                            text = duration,
                            style = MaterialTheme.typography.body2,
                            color = DurationColor,
                        )
                    }
                }

                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.body1,
                    color = SubtitleColor,
                )
            }
        }
    }
}

@Composable
private fun TimelineMarker(
    isLast: Boolean,
    indicatorText: String,
    indicatorColor: Color,
) {
    Column(
        modifier = Modifier.height(92.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(
            modifier = Modifier
                .size(34.dp)
                .background(color = Color.White, shape = CircleShape)
                .border(width = 2.dp, color = indicatorColor, shape = CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = indicatorText,
                color = indicatorColor,
                style = MaterialTheme.typography.h6.copy(fontWeight = FontWeight.Bold),
            )
        }

        if (!isLast) {
            Box(
                modifier = Modifier
                    .padding(top = 4.dp)
                    .width(2.dp)
                    .fillMaxHeight()
                    .background(TimelineLine),
            )
        }
    }
}

@Preview
@Composable
private fun WorkflowExecutionPathCardPreview() {
    MaterialTheme {
        WorkflowExecutionPathCard(
            title = "Validate Input Payload",
            subtitle = "Schema validation successful for user_v2 object.",
            duration = "0.4s",
        )
    }
}
