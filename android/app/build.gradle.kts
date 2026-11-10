plugins { id("com.android.application") }

android {
    namespace = "com.wowsuperapp.mobile"
    compileSdk = 36
    defaultConfig {
        applicationId = "com.wowsuperapp.mobile"
        minSdk = 24
        targetSdk = 36
        versionCode = 2
        versionName = "1.0.1"
    }

    val signingPath = System.getenv("WOW_UPLOAD_KEYSTORE_PATH")
    val signingPassword = System.getenv("WOW_UPLOAD_KEYSTORE_PASSWORD")
    val signingAlias = System.getenv("WOW_UPLOAD_KEY_ALIAS")
    val signingKeyPassword = System.getenv("WOW_UPLOAD_KEY_PASSWORD")
    val hasSigning = listOf(signingPath, signingPassword, signingAlias, signingKeyPassword)
        .all { !it.isNullOrBlank() }

    if (hasSigning) {
        signingConfigs {
            create("upload") {
                storeFile = file(signingPath!!)
                storePassword = signingPassword!!
                keyAlias = signingAlias!!
                keyPassword = signingKeyPassword!!
            }
        }
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            if (hasSigning) signingConfig = signingConfigs.getByName("upload")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
