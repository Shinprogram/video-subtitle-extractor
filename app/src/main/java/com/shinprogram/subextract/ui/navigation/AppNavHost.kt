package com.shinprogram.subextract.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.shinprogram.subextract.ui.screens.editor.EditorScreen
import com.shinprogram.subextract.ui.screens.home.HomeScreen
import com.shinprogram.subextract.ui.screens.player.PlayerScreen
import com.shinprogram.subextract.ui.screens.settings.SettingsScreen

object Routes {
    const val HOME = "home"
    const val SETTINGS = "settings"
    const val PLAYER = "player/{videoUri}"
    const val EDITOR = "editor"

    fun player(videoUri: String) = "player/${android.net.Uri.encode(videoUri)}"
}

@Composable
fun AppNavHost() {
    val nav = rememberNavController()
    NavHost(navController = nav, startDestination = Routes.HOME) {
        composable(Routes.HOME) {
            HomeScreen(
                onOpenSettings = { nav.navigate(Routes.SETTINGS) },
                onVideoPicked = { uri -> nav.navigate(Routes.player(uri.toString())) },
            )
        }
        composable(Routes.SETTINGS) { SettingsScreen(onBack = { nav.popBackStack() }) }
        composable(
            Routes.PLAYER,
            arguments = listOf(navArgument("videoUri") { type = NavType.StringType }),
        ) { backStackEntry ->
            val raw = backStackEntry.arguments?.getString("videoUri").orEmpty()
            PlayerScreen(
                videoUri = android.net.Uri.parse(android.net.Uri.decode(raw)),
                onBack = { nav.popBackStack() },
                onEdit = { nav.navigate(Routes.EDITOR) },
            )
        }
        composable(Routes.EDITOR) { EditorScreen(onBack = { nav.popBackStack() }) }
    }
}
