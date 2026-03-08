# App 提交巡查记录问题诊断与修复报告

**报告日期**: 2026-03-09  
**问题描述**: 用户在 app 上提交巡查记录后，网页后台没有对应显示  
**诊断状态**: ✅ 问题已识别并修复

---

## 🔍 问题诊断

### 检查步骤

#### 1. 数据库验证 ✅
- **检查**: 数据库中是否有巡查记录
- **结果**: 初始为空，通过 Django shell 创建测试记录成功
- **结论**: 数据库本身没问题

#### 2. API 端点验证 ✅
- **检查**: 前端是否使用正确的 API 端点
- **发现**: 前端向 `/inspections/create/` 发送请求，但后端 DRF 路由是 `/inspections/`
- **问题等级**: **严重**

#### 3. ContentType 验证 ✅
- **检查**: 发送 FormData 时是否正确设置 ContentType
- **发现**: `BaseOptions` 中固定设置 `contentType: 'application/json'`
- **影响**: 发送 `multipart/form-data` 时被覆盖，导致后端无法正确解析文件
- **问题等级**: **严重**

#### 4. 认证令牌验证 ✅
- **检查**: 请求是否包含有效的认证令牌
- **结果**: 拦截器配置正确，会自动附加 `Authorization: Bearer {token}` 头
- **结论**: 认证部分没问题

---

## 🐛 根本原因

### 问题 1: API 端点不匹配

**位置**: `app/lib/config/api_config.dart`  
**原始代码**:
```dart
static const String createInspectionEndpoint = '/inspections/create/';
```

**问题**: 
- DRF 的 `DefaultRouter` 注册 `InspectionViewSet` 会生成以下路由：
  - `POST /inspections/` → 创建新记录（DRF 自动调用 `.create()` 方法）
  - `GET /inspections/` → 列表
  - `GET /inspections/{id}/` → 详情
  - 等等

- 但前端尝试访问 `/inspections/create/`，这不是 DRF 生成的路由
- 因此请求返回 **404 Not Found**，数据永远无法到达服务器

**DRF 路由规则**:
```python
router = DefaultRouter()
router.register(r'inspections', api_views.InspectionViewSet)
# 自动生成的路由：
# POST /inspections/ → create 动作
# 不包括 /inspections/create/ 这个路由
```

---

### 问题 2: ContentType 被固定为 JSON

**位置**: `app/lib/services/api_service.dart`  
**原始代码**:
```dart
_dio = Dio(
  BaseOptions(
    baseUrl: ApiConfig.baseUrl,
    contentType: 'application/json',  // ❌ 固定为JSON
    ...
  ),
);
```

**问题**:
- 当发送 `FormData` 时，Dio 需要自动设置 `Content-Type: multipart/form-data`
- 但 `BaseOptions` 中的固定 `contentType: 'application/json'` 会干扰这个自动设置
- 导致请求头错误，后端无法正确解析多部分表单数据（或返回 400/415 错误）

**MultipartFile 的正确处理流程**:
```
FormData.fromMap({
  'photo': MultipartFile.fromFile(...)  // 这需要 multipart/form-data
})
```

---

## ✅ 已实施的修复

### 修复 1: 更正 API 端点（关键修复）

**文件**: `app/lib/config/api_config.dart`  
**修改**:
```dart
// 修改前
static const String createInspectionEndpoint = '/inspections/create/';

// 修改后
static const String createInspectionEndpoint = '/inspections/';  // 标准REST端点
```

**原因**: 
- 遵循 RESTful API 规范
- 与 DRF 生成的路由一致
- `POST /inspections/` 即表示 "创建新的巡查记录"

---

### 修复 2: 移除固定的 ContentType（关键修复）

**文件**: `app/lib/services/api_service.dart`  
**修改**:
```dart
// 修改前
_dio = Dio(
  BaseOptions(
    baseUrl: ApiConfig.baseUrl,
    contentType: 'application/json',  // ❌ 移除此行
    ...
  ),
);

// 修改后
_dio = Dio(
  BaseOptions(
    baseUrl: ApiConfig.baseUrl,
    // 不设置contentType，让dio根据数据类型自动设置：
    // - JSON请求 → application/json
    // - FormData请求 → multipart/form-data
    ...
  ),
);
```

**效果**:
- JSON 请求自动使用 `application/json`
- FormData 请求（含文件）自动使用 `multipart/form-data`
- 后端能正确解析所有请求

---

## 📊 修复前后的数据流

### 修复前（❌ 失败）
```
Flutter App
  ↓
POST /inspections/create/ + JSON
  ↓ (错误的端点)
404 Not Found
  ↓
数据未到达后端
  ↓
❌ 网页后台无法显示
```

### 修复后（✅ 成功）
```
Flutter App
  ↓
POST /inspections/ + multipart/form-data
  ↓ (正确的端点和格式)
Django 后端接收
  ↓
DRF InspectionViewSet.create()
  ↓
保存到数据库
  ↓
✅ 网页后台可以查看
```

---

## 🔧 验证步骤

### 1. 后端验证 ✅
```bash
cd path/to/heritage_system
python manage.py runserver 0.0.0.0:8000

# 验证端点
curl -X GET http://localhost:8000/api/inspections/ \
  -H "Authorization: Bearer {YOUR_TOKEN}"
```

### 2. 前端验证
- [ ] 更新 `api_config.dart` 中的端点
- [ ] 更新 `api_service.dart` 中的 ContentType 配置
- [ ] 运行 `flutter pub get`
- [ ] 重新编译并部署

### 3. 端到端测试
```
1. 在手机上打开 app
2. 登录
3. 选择文物点
4. 拍照
5. 提交巡查记录
6. 检查网页后台是否显示
   位置：管理后台 → 日常办公 → 巡查记录
```

---

## 📝 关键要点总结

| 问题 | 原因 | 影响 | 修复 |
|------|------|------|------|
| 端点不正确 | 使用了 `/inspections/create/` 而不是 `/inspections/` | **404 错误，数据完全无法到达** | 改为 `/inspections/` |
| ContentType 固定 | `BaseOptions` 中硬编码 `application/json` | **无法正确处理文件上传** | 移除固定设置，让 dio 自动判断 |
| 认证错误 | 无 | 无 | 无需修复（已正确处理） |

---

## 🚀 后续建议

### 立即需要做
1. ✅ 已修改 API 端点
2. ✅ 已修改 ContentType 配置
3. [ ] 编译并测试应用

### 长期建议
1. **添加错误日志**
   - 在前端添加更详细的错误日志，方便调试
   - 在后端 API 中记录所有请求和错误

2. **API 文档**
   - 为 REST API 端点添加完整的文档
   - 明确标注 ContentType 和请求格式

3. **单元测试**
   ```dart
   // 测试FormData请求
   test('uploadInspectionPhoto sends correct ContentType', () {
     // 验证FormData请求使用multipart/form-data
   });
   ```

4. **集成测试**
   - 定期测试从 app 提交数据到网页后台的完整流程

---

## 📋 检查清单

- [x] 识别 API 端点不匹配问题
- [x] 识别 ContentType 配置问题
- [x] 修改 `api_config.dart`
- [x] 修改 `api_service.dart`
- [x] 验证数据库正常工作
- [x] 验证后端 API 配置正确
- [ ] 重新编译 Flutter 应用
- [ ] 端到端测试
- [ ] 部署到生产环境

---

## 🎯 预期结果

修复后，用户提交的巡查记录应该能：
1. ✅ 成功上传到服务器
2. ✅ 保存到数据库
3. ✅ 在网页后台"巡查记录"中显示
4. ✅ 包含所有字段：位置、照片、时间、问题描述等

---

**报告完成时间**: 2026-03-09 23:59  
**修复状态**: 已完成 ✅  
**测试状态**: 待验证 ⏳
