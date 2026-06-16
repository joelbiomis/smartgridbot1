package com.example.data

import com.example.api.BotApiService
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import java.util.concurrent.TimeUnit

object ServerConfig {
    private var _baseUrl: String = "http://10.0.2.2:8000/"
    val baseUrl: String get() = _baseUrl

    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BODY
    }

    private val okHttpClient = OkHttpClient.Builder()
        .addInterceptor(loggingInterceptor)
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    private val moshi = Moshi.Builder()
        .add(KotlinJsonAdapterFactory())
        .build()

    @Volatile
    private var _api: BotApiService? = null
    val api: BotApiService
        get() {
            if (_api == null) {
                _api = buildRetrofit().create(BotApiService::class.java)
            }
            return _api!!
        }

    private fun buildRetrofit(): Retrofit {
        return Retrofit.Builder()
            .baseUrl(_baseUrl)
            .client(okHttpClient)
            .addConverterFactory(MoshiConverterFactory.create(moshi))
            .build()
    }

    fun updateBaseUrl(newUrl: String) {
        val normalized = if (newUrl.endsWith("/")) newUrl else "$newUrl/"
        _baseUrl = normalized
        _api = buildRetrofit().create(BotApiService::class.java)
    }
}
