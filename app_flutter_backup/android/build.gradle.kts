allprojects {
    repositories {
// 使用带有等号和 uri 函数的标准 Kotlin 语法
// 1. 优先添加 Flutter 官方国内镜像（非常关键！）
// 1. Flutter 引擎专用镜像
        maven { url = uri("https://storage.flutter-io.cn/download.flutter.io") }
        
        // 2. 阿里云的 Google 和 MavenCentral 镜像（最全）
        maven { url = uri("https://maven.aliyun.com/repository/google") }
        maven { url = uri("https://maven.aliyun.com/repository/public") }
        
        // 3. 官方源作为兜底
        google()
        mavenCentral()
        
        // 4. JCenter 放在最后（它已经半废弃了）
        maven { url = uri("https://maven.aliyun.com/repository/jcenter") }
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}
subprojects {
    project.evaluationDependsOn(":app")
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
