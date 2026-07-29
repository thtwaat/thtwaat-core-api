package com.thtwaat.starter.core.network

class ApiException(
    message: String,
    val status: Int? = null,
    val code: String? = null,
) : Exception(message)
