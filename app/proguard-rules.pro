# Keep Paddle Lite JNI entrypoints when they are wired in.
-keep class com.shinprogram.subextract.ocr.paddle.** { *; }
-keepclasseswithmembernames class * { native <methods>; }

# Kotlinx Serialization
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.SerializationKt
-keep,includedescriptorclasses class com.shinprogram.subextract.**$$serializer { *; }
-keepclassmembers class com.shinprogram.subextract.** {
    *** Companion;
}
-keepclasseswithmembers class com.shinprogram.subextract.** {
    kotlinx.serialization.KSerializer serializer(...);
}

# Hilt / Dagger
-keep class dagger.hilt.** { *; }
-keep class javax.inject.** { *; }

# OkHttp / Retrofit
-dontwarn okio.**
-dontwarn okhttp3.**
-dontwarn retrofit2.**
-keepattributes Signature, Exceptions

# Media3 / ExoPlayer
-keep class androidx.media3.** { *; }

# Keep Room entities
-keep @androidx.room.Entity class * { *; }
