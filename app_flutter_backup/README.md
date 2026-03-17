# 文物巡查系统 - Flutter 看护员端

一个用 Flutter + Dart 开发的移动应用，专为文物看护员设计，支持快速巡查文物点并上报带有时间和经纬度坐标的照片。

## 主要功能

### 1. **用户认证**
- 用户名/密码登录
- 基于 Token 的认证机制
- 与后端系统联动

### 2. **附近文物点搜索**
- 基于 GPS 定位获取用户当前位置
- 实时检索附近 5km 范围内的文物点
- 显示文物点名称、地址、保护级别等信息
- 距离信息展示

### 3. **快速巡查与拍照上报**
- **拍摄照片**: 使用设备相机直接拍摄现场照片
- **相册导入**: 从相册选择已有照片
- **GPS 坐标记录**: 自动记录照片拍摄时的经纬度
- **时间戳**: 自动记录巡查时间
- **异常报告**: 标记文物异常状态并详细描述问题

### 4. **离线存储与同步**
- 本地 SQLite 数据库存储未上传的记录
- 自动和手动同步到服务器
- 网络连接恢复后自动重试

### 5. **巡查历史与统计**
- 查看完整的巡查记录历史
- 显示状态（正常/异常）、上传状态
- 统计未上传的记录数量

## 技术栈

- **框架**: Flutter 3.41+
- **语言**: Dart 3.11+
- **状态管理**: Riverpod 2.4+
- **网络库**: Dio 5.3+
- **本地存储**: SQLite + SharedPreferences
- **定位服务**: Geolocator 10.1+
- **相机/图片**: Camera 0.10+ 和 Image Picker 1.0+
- **权限管理**: Permission Handler 11.4+

## 快速开始

### 1. 获取依赖

```bash
cd app
flutter pub get
```

### 2. 配置后端 API

编辑 `lib/config/api_config.dart`，设置正确的后端服务器地址：

```dart
static const String baseUrl = 'http://127.0.0.1:8000/api';
```

### 3. 运行应用

```bash
# 开发模式运行
flutter run

# 在特定设备上运行
flutter run -d <device_id>

# 列出可用设备
flutter devices
```

### 4. 构建发布版本

```bash
# Android APK
flutter build apk --release

# iOS
flutter build ios --release
```

## 项目结构

```
lib/
├── main.dart                        # 应用入口
├── config/
│   └── api_config.dart             # API 配置
├── models/                          # 数据模型
│   ├── heritage_site.dart          # 文物点模型
│   ├── inspection_record.dart      # 巡查记录模型
│   ├── user.dart                   # 用户模型
│   └── index.dart                  # 导出文件
├── services/                        # 业务服务层
│   ├── api_service.dart            # API 网络服务
│   ├── storage_service.dart        # 本地存储服务
│   ├── location_service.dart       # GPS 定位服务
│   ├── camera_service.dart         # 相机和图片服务
│   └── index.dart                  # 导出文件
├── providers/                       # Riverpod 状态管理
│   ├── auth_provider.dart          # 认证状态
│   ├── heritage_provider.dart      # 文物点数据
│   ├── inspection_provider.dart    # 巡查记录数据
│   └── index.dart                  # 导出文件
└── screens/                         # UI 界面
    ├── login_screen.dart           # 登录界面
    ├── home_screen.dart            # 主屏幕/附近文物
    ├── inspection_detail_screen.dart # 巡查详情（拍照）
    ├── inspection_history_screen.dart # 巡查历史
    └── index.dart                  # 导出文件
```

## 核心 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/auth/login/` | POST | 用户登录 |
| `/auth/user/` | GET | 获取当前用户信息 |
| `/heritages/nearby/` | GET | 获取附近的文物点 |
| `/inspections/create/` | POST | 创建/上传巡查记录 |
| `/inspections/my-records/` | GET | 获取我的巡查记录 |
| `/inspections/statistics/` | GET | 获取统计信息 |

## 权限配置

### Android 权限

已在 `AndroidManifest.xml` 中配置：
- `ACCESS_FINE_LOCATION` - 精确定位
- `ACCESS_COARSE_LOCATION` - 粗略定位  
- `CAMERA` - 相机
- `READ_EXTERNAL_STORAGE` - 读取存储
- `WRITE_EXTERNAL_STORAGE` - 写入存储
- `INTERNET` - 网络访问

### iOS 权限

需要在 `ios/Runner/Info.plist` 中添加：

```xml
<key>NSLocationWhenInUseUsageDescription</key>
<string>需要您的位置信息来获取附近的文物点</string>
<key>NSCameraUsageDescription</key>
<string>需要访问相机来拍摄现场照片</string>
<key>NSPhotoLibraryUsageDescription</key>
<string>需要访问相册来选择照片</string>
```

## 使用流程

1. **登录** - 输入看护员账号和密码
2. **查看附近文物** - 系统自动定位并显示 5km 范围内的文物点
3. **进入巡查** - 点击要巡查的文物点
4. **拍照记录** - 拍摄现场照片或从相册选择
5. **标记状态** - 标记文物状态（正常/异常）
6. **提交报告** - 提交记录，自动上传照片和位置信息
7. **查看历史** - 在历史页面查看所有巡查记录

## 常见问题

- **没有权限?** - 在系统设置中授予位置、相机权限
- **照片上传失败?** - 检查网络连接，使用「同步」功能重试
- **如何修改 API 地址?** - 编辑 `lib/config/api_config.dart` 中的 `baseUrl`

## 开发环境要求

- Flutter 3.11.1+
- Dart 3.11.1+
- iOS 12.0+ (iPhone)
- Android API 21+ (Android 5.0+)

---

更新日期: 2026 年 3 月 9 日
