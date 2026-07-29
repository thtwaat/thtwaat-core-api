package com.thtwaat.starter.di

import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent

/** Repositories are constructor-injected via Hilt (@Singleton + @Inject). */
@Module
@InstallIn(SingletonComponent::class)
object RepositoryModule
