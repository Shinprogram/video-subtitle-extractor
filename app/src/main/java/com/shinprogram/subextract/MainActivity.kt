package com.shinprogram.subextract

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.shinprogram.subextract.ui.navigation.AppNavHost
import com.shinprogram.subextract.ui.theme.SubExtractTheme
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            SubExtractTheme {
                AppNavHost()
            }
        }
    }
}
