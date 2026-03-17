# Flutter 应用快速部署指南

## 1. 初始化与配置

### 步骤 1: 修改 API 服务器地址

编辑 `lib/config/api_config.dart`:

```dart
// 修改这一行为你的后端服务器地址
static const String baseUrl = 'http://192.168.x.x:8000/api';
```

例如，如果后端运行在本地:
```dart
static const String baseUrl = 'http://127.0.0.1:8000/api';
```

### 步骤 2: 安装依赖

```bash
cd app
flutter pub get
```

### 步骤 3: 生成代码（如需要）

```bash
flutter pub run build_runner build
```

## 2. 开发模式运行

### 在模拟器上运行

```bash
# 列出可用的设备/模拟器
flutter devices

# 在特定设备上运行
flutter run -d <device_id>

# 快速热重载开发
- 修改代码后，按 'r' 进行热重载
- 按 'R' 进行热重启
```

### 在真机上运行

#### Android:
```bash
# 启用 USB 调试后连接设备
adb devices  # 应该能看到设备列表
flutter run
```

#### iOS:
```bash
# 需要 Xcode 和开发证书
open ios/Runner.xcworkspace
# 或者使用命令行
flutter run -d <device_id>
```

## 3. 常用命令

```bash
# 查看 Flutter 版本信息
flutter --version

# 检查开发环境
flutter doctor

# 清理项目
flutter clean

# 获取最新依赖
flutter pub get
flutter pub upgrade

# 格式化代码
dart format lib/

# 分析代码问题
flutter analyze

# 查看日志
flutter logs

# 调试模式构建 APK
flutter build apk --debug

# 发布模式构建 APK
flutter build apk --release

# 构建 iOS
flutter build ios --release
```

## 4. 打包和发布

### Android APK 构建

```bash
# 开发版本
flutter build apk --debug

# 发布版本（推荐）
flutter build apk --release

# 输出位置: build/app/outputs/flutter-apk/app-release.apk
```

### Android App Bundle（用于 Google Play）

```bash
flutter build appbundle --release
# 输出位置: build/app/outputs/bundle/release/app-release.aab
```

### iOS 构建

```bash
flutter build ios --release
# 输出位置: build/ios/iphoneos/
```

## 5. 后端 API 对接需求

确保后端提供以下 API 端点，按照指定的数据格式：

### 登录接口
```
POST /api/auth/login/
请求体:
{
  "username": "string",
  "password": "string"
}

响应 (200):
{
  "token": "string",
  "user": {
    "id": integer,
    "username": "string",
    "email": "string",
    "first_name": "string",
    "last_name": "string",
    "is_staff": boolean
  }
}
```

### 获取附近文物点接口
```
GET /api/heritages/nearby/?latitude=39.9&longitude=116.4&radius=5.0
响应 (200):
[
  {
    "id": integer,
    "name": "string",
    "sip_code": "string",
    "category": "string",
    "level": "string",
    "address": "string",
    "longitude": float,
    "latitude": float,
    "description": "string",
    "manager": "string",
    "distance": float  // 可选，单位 km
  }
]
```

### 上传巡查记录接口
```
POST /api/inspections/create/
Content-Type: multipart/form-data

参数:
- site: integer (文物点 ID)
- latitude: float (纬度，可选)
- longitude: float (经度，可选)
- is_normal: boolean (是否正常)
- issue_details: string (问题描述，可选)
- photo: file (照片文件，可选)

响应 (201):
{
  "id": integer,
  "site": integer,
  "photo": "string (URL)或文件路径",
  "latitude": float,
  "longitude": float,
  "inspect_time": "ISO8601 datetime",
  "is_normal": boolean,
  "issue_details": "string"
}
```

### 获取巡查记录
```
GET /api/inspections/my-records/?page=1&page_size=20
响应 (200):
[
  {
    "id": integer,
    "site": integer,
    "photo": "string (URL)",
    "latitude": float,
    "longitude": float,
    "inspect_time": "ISO8601 datetime",
    "is_normal": boolean,
    "issue_details": "string"
  }
]
```

## 6. 故障排查

### 构建失败

```bash
# 清理所有缓存
flutter clean
flutter pub get

# 重新构建
flutter run
```

### iOS 特定问题

```bash
cd ios
rm -rf Pods
pod install --repo-update
cd ..
flutter run
```

### 网络错误

- 检查 `lib/config/api_config.dart` 中的 API 地址
- 确保设备/模拟器能访问后端服务器
- 检查防火墙和代理设置

### 权限错误

- 确保 `AndroidManifest.xml` 中有所需的权限声明
- 对于 Android 6.0+，需要在运行时请求权限
- 检查 `ios/Runner/Info.plist` 中的权限描述

## 7. 开发提示

### 热重载工作流
1. 修改代码
2. 按 `r` 进行热重载（仅 UI 变更）
3. 按 `R` 进行热重启（需要重新运行到 main）
4. 若热重载失败，使用 `flutter run` 重新启动

### 调试
- 使用 `print()` 或 `debugPrint()` 进行日志输出
- 运行 `flutter logs` 查看实时日志
- 使用 Dart DevTools: `flutter pub global activate devtools`

### 性能优化
- 使用 `--profile` 或 `--release` 模式测试
- 使用 DevTools 的 Performance 标签页
- 监控内存使用情况

## 8. 应用交付清单

发布前检查：

- [ ] 修改 `lib/config/api_config.dart` 中的 API 地址
- [ ] 更新应用版本号（`pubspec.yaml` 中的 `version`）
- [ ] 更新应用图标和名称
- [ ] 测试所有功能（登录、定位、拍照、上传）
- [ ] 测试离线能力和同步功能
- [ ] 检查权限提示文案
- [ ] 进行 `flutter analyze` 代码检查
- [ ] 使用 `--release` 模式构建并测试
- [ ] 获取签名证书（Android）
- [ ] 生成最终的 APK 或 IPA 文件

## 9. 版本更新

修改 `pubspec.yaml`:

```yaml
version: 1.0.0+1
```

格式: `major.minor.patch+buildNumber`

例如:
- 1.0.0+1 - 首次发布
- 1.0.1+2 - 修复版本
- 1.1.0+3 - 功能更新

## 10. 常见问题快速解答

**Q: 应用启动时崩溃？**
A: 执行 `flutter clean && flutter pub get && flutter run`

**Q: 定位功能不工作？**
A: 检查权限申请和 `LocationService` 初始化

**Q: 照片上传失败？**
A: 检查网络连接和后端 `/inspections/create/` 接口

**Q: 构建 APK 太慢？**
A: 使用 `--split-per-abi` 选项分离架构

---

更新时间: 2026 年 3 月 9 日
