package com.lilambera.clipbox

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "settings")

private val KEY_SERVER_URL = stringPreferencesKey("server_url")
private val KEY_TOKEN = stringPreferencesKey("token")

class SettingsStore(private val context: Context) {

    suspend fun getServerUrl(): String {
        return context.dataStore.data
            .map { it[KEY_SERVER_URL] ?: "" }
            .first()
    }

    suspend fun getToken(): String {
        return context.dataStore.data
            .map { it[KEY_TOKEN] ?: "" }
            .first()
    }

    suspend fun save(serverUrl: String, token: String) {
        context.dataStore.edit { prefs ->
            prefs[KEY_SERVER_URL] = serverUrl
            prefs[KEY_TOKEN] = token
        }
    }
}