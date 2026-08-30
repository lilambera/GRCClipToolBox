package com.lilambera.clipbox

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier

@Composable
fun  MainScreen(){
    var selectedTab by remember { mutableIntStateOf(0)}

    var tabs = listOf("烧录", "下载", "Whisper", "设置")

    Scaffold(
        bottomBar = {
            NavigationBar {
                tabs.forEachIndexed { index, title ->
                    NavigationBarItem(
                        selected = selectedTab == index,
                        onClick = { selectedTab = index},
                        icon = {
                            Icon(
                                imageVector = when (index) {
                                    0 -> Icons.Default.PlayArrow
                                    1 -> Icons.Default.Add
                                    2 -> Icons.Default.Star
                                    else -> Icons.Default.Settings
                                },
                                contentDescription = title
                            )
                        }
                    )
                }
            }
        }
    ){innerPadding ->
        Box(
            modifier = Modifier
                .padding(innerPadding)
                .fillMaxSize()
        ){
            when (selectedTab) {
                0 -> CenteredText("烧录（还没做）")
                1 -> CenteredText("下载（还没做）")
                2 -> CenteredText("Whisper（还没做）")
                else -> SettingsScreen()
            }
        }
    }
}

@Composable
private fun CenteredText(text: String) {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        Text(text)
    }
}