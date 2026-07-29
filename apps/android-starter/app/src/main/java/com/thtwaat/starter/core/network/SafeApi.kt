package com.thtwaat.starter.core.network

import com.thtwaat.starter.core.util.Result
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import retrofit2.HttpException
import java.io.IOException

suspend fun <T> safeApiCall(block: suspend () -> T): Result<T> {
    return try {
        Result.Success(block())
    } catch (e: HttpException) {
        val body = e.response()?.errorBody()?.string().orEmpty()
        val message = parseDetail(body) ?: e.message() ?: "HTTP ${e.code()}"
        Result.Error(message = message, status = e.code(), code = "http_error")
    } catch (e: IOException) {
        Result.Error(message = e.message ?: "Network error", code = "network_error")
    } catch (e: Exception) {
        Result.Error(message = e.message ?: "Unknown error", code = "unknown")
    }
}

private fun parseDetail(body: String): String? {
    if (body.isBlank()) return null
    return try {
        val element = Json.parseToJsonElement(body).jsonObject
        element["detail"]?.jsonPrimitive?.content
            ?: element["message"]?.jsonPrimitive?.content
    } catch (_: Exception) {
        null
    }
}
