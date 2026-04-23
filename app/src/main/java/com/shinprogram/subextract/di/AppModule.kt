package com.shinprogram.subextract.di

import android.content.Context
import com.shinprogram.subextract.data.datastore.SettingsRepositoryImpl
import com.shinprogram.subextract.data.db.AppDatabase
import com.shinprogram.subextract.data.db.SubtitleTrackDao
import com.shinprogram.subextract.data.repository.SubtitleTrackRepositoryImpl
import com.shinprogram.subextract.domain.repository.SettingsRepository
import com.shinprogram.subextract.domain.repository.SubtitleExtractorRepository
import com.shinprogram.subextract.domain.repository.SubtitleTrackRepository
import com.shinprogram.subextract.domain.repository.TranslationRepository
import com.shinprogram.subextract.ocr.SubtitleExtractor
import com.shinprogram.subextract.translate.GeminiService
import com.shinprogram.subextract.translate.TranslationRepositoryImpl
import dagger.Binds
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object DataModule {

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext ctx: Context): AppDatabase = AppDatabase.create(ctx)

    @Provides
    @Singleton
    fun provideTrackDao(db: AppDatabase): SubtitleTrackDao = db.trackDao()

    @Provides
    @Singleton
    fun provideJson(): Json = Json { ignoreUnknownKeys = true; isLenient = true }

    @Provides
    @Singleton
    fun provideOkHttp(): OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .addInterceptor(HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BASIC })
        .build()

    @Provides
    @Singleton
    fun provideRetrofit(client: OkHttpClient, json: Json): Retrofit = Retrofit.Builder()
        .baseUrl("https://generativelanguage.googleapis.com/")
        .client(client)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()

    @Provides
    @Singleton
    fun provideGeminiService(retrofit: Retrofit): GeminiService = retrofit.create(GeminiService::class.java)
}

@Module
@InstallIn(SingletonComponent::class)
abstract class BindingsModule {
    @Binds abstract fun bindExtractor(impl: SubtitleExtractor): SubtitleExtractorRepository
    @Binds abstract fun bindTrackRepo(impl: SubtitleTrackRepositoryImpl): SubtitleTrackRepository
    @Binds abstract fun bindTranslation(impl: TranslationRepositoryImpl): TranslationRepository
    @Binds abstract fun bindSettings(impl: SettingsRepositoryImpl): SettingsRepository
}
