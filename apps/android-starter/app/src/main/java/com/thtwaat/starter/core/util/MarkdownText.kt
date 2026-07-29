package com.thtwaat.starter.core.util

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.sp

@Composable
fun MarkdownText(text: String) {
    val annotated = buildAnnotatedString {
        text.lines().forEachIndexed { index, line ->
            when {
                line.startsWith("### ") -> withStyle(SpanStyle(fontWeight = FontWeight.Bold, fontSize = 18.sp)) {
                    append(line.removePrefix("### ")); append('\n')
                }
                line.startsWith("## ") -> withStyle(SpanStyle(fontWeight = FontWeight.Bold, fontSize = 20.sp)) {
                    append(line.removePrefix("## ")); append('\n')
                }
                line.startsWith("# ") -> withStyle(SpanStyle(fontWeight = FontWeight.Bold, fontSize = 22.sp)) {
                    append(line.removePrefix("# ")); append('\n')
                }
                else -> {
                    var i = 0
                    while (i < line.length) {
                        when {
                            line.startsWith("**", i) -> {
                                val end = line.indexOf("**", i + 2)
                                if (end > i) {
                                    withStyle(SpanStyle(fontWeight = FontWeight.Bold)) { append(line.substring(i + 2, end)) }
                                    i = end + 2
                                } else {
                                    append(line[i]); i++
                                }
                            }
                            line.startsWith("`", i) -> {
                                val end = line.indexOf('`', i + 1)
                                if (end > i) {
                                    withStyle(SpanStyle(fontFamily = FontFamily.Monospace)) { append(line.substring(i + 1, end)) }
                                    i = end + 1
                                } else {
                                    append(line[i]); i++
                                }
                            }
                            else -> { append(line[i]); i++ }
                        }
                    }
                    if (index != text.lines().lastIndex) append('\n')
                }
            }
        }
    }
    Text(text = annotated, style = MaterialTheme.typography.bodyLarge)
}
