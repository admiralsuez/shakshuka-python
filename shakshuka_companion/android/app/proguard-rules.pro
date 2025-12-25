# Flutter specific rules
-keep class io.flutter.app.** { *; }
-keep class io.flutter.plugin.** { *; }
-keep class io.flutter.util.** { *; }
-keep class io.flutter.view.** { *; }
-keep class io.flutter.** { *; }
-keep class io.flutter.plugins.** { *; }

# Keep native methods
-keepclasseswithmembernames class * {
    native <methods>;
}

# Keep Parcelables
-keepclassmembers class * implements android.os.Parcelable {
    static ** CREATOR;
}

# Keep Serializable classes
-keepclassmembers class * implements java.io.Serializable {
    static final long serialVersionUID;
    private static final java.io.ObjectStreamField[] serialPersistentFields;
    private void writeObject(java.io.ObjectOutputStream);
    private void readObject(java.io.ObjectInputStream);
    java.lang.Object writeReplace();
    java.lang.Object readResolve();
}

# Hive database
-keep class * extends com.google.protobuf.GeneratedMessageLite { *; }

# Keep R classes
-keepclassmembers class **.R$* {
    public static <fields>;
}

# Don't warn about missing classes
-dontwarn kotlin.**
-dontwarn org.jetbrains.**

# Play Core library - not used but referenced by Flutter
-dontwarn com.google.android.play.core.**
-keep class com.google.android.play.core.** { *; }

# Flutter deferred components (not used)
-dontwarn io.flutter.app.FlutterPlayStoreSplitApplication
-dontwarn io.flutter.embedding.engine.deferredcomponents.**
