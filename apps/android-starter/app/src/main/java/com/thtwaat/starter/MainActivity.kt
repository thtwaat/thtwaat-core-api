package com.thtwaat.starter

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.thtwaat.starter.ui.navigation.ThtwaatNavHost
import com.thtwaat.starter.ui.theme.ThtwaatTheme
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            ThtwaatTheme {
                ThtwaatNavHost()
            }
        }
    }
}