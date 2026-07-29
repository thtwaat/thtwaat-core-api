-keepattributes *Annotation*, InnerClasses, EnclosingMethod, Signature
-keepclassmembers class ** {
    @kotlinx.serialization.Serializable <fields>;
}
-dontwarn okhttp3.**
-dontwarn retrofit2.**
-dontwarn kotlinx.serialization.**
