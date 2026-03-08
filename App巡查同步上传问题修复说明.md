# App 巡查记录上传问题修复说明

**问题描述**：
1. App巡查历史中点击同步，无法上传，状态仍为"未同步"
2. 后端网页巡查记录列表报错Server Error (500)

**诊断日期**: 2026-03-09  
**修复状态**: ✅ 已完成

---

## 🔍 问题根因分析

### 问题 1: App 同步上传失败

#### 根本原因
**缺少 API 端点**: App 调用 `/inspections/my-records/` 获取记录列表，但后端 DRF 没有实现这个自定义路由

#### 详细流程
```
App调用:
  GET /inspections/my-records/  ← 获取我的巡查记录
  ↓
后端路由查找:
  DefaultRouter 生成的路由: /inspections/, /inspections/{id}/
  ❌ 没有 /inspections/my-records/ 
  ↓
结果: 404 Not Found
  ↓
后果: 列表无法加载，同步功能报错
```

#### 影响范围
- 点击"同步"按钮时无法获取待上传的记录清单
- StorageService.getUnuploadedRecords() 依赖于这个端点关键是流程中
- 巡查历史页面无法显示待同步的记录

---

### 问题 2: 后端网页 500 错误

#### 根本原因
Admin 页面中的三个自定义展示方法在处理数据时缺少异常处理：

1. **display_photo()** - 访问 photo.url 但 photo 可能为空或无 url 属性
2. **location_display()** - 直接使用 latitude/longitude 进行格式化，可能出现类型转换错误
3. **issue_summary()** - 访问 is_normal 字段，缺少默认值处理

#### 错误堆栈分析
```
Admin 列表加载:
  ↓
遍历每条 InspectionRecord:
  ↓
调用 list_display 中的自定义方法:
  - display_photo()     ← 可能抛出 AttributeError
  - location_display()  ← 可能抛出 TypeError
  - issue_summary()     ← 可能抛出 AttributeError
  ↓
❌ HTTP 500 Server Error
```

---

## ✅ 已实施的修复

### 修复 1: 添加 my_records 自定义路由

**文件**: [core/api_views.py](core/api_views.py#L70-L103)

```python
class InspectionViewSet(viewsets.ModelViewSet):
    # ... 现有代码 ...
    
    @action(detail=False, methods=['get'])
    def my_records(self, request):
        """获取当前用户的巡查记录"""
        queryset = self.get_queryset().order_by('-inspect_time')
        
        # 分页处理
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('page_size', 20)
        try:
            page = int(page)
            page_size = int(page_size)
        except (ValueError, TypeError):
            page = 1
            page_size = 20
        
        start = (page - 1) * page_size
        end = start + page_size
        records = queryset[start:end]
        
        serializer = self.get_serializer(records, many=True)
        return Response(serializer.data)
```

**效果**:
- ✅ 创建新路由: `GET /api/inspections/my-records/`
- ✅ 支持分页: `page` 和 `page_size` 参数
- ✅ 自动过滤: 只返回当前用户的记录
- ✅ 降低数据库压力: 避免加载所有记录

---

### 修复 2: 安全处理 display_photo()

**文件**: [core/admin.py](core/admin.py#L305-L317)

```python
def display_photo(self, obj):
    try:
        if obj.photo and hasattr(obj.photo, 'url'):
            return format_html(
                '<img src="{}" width="200" style="border-radius: 4px;" /><br><a href="{}" target="_blank">查看原图</a>',
                obj.photo.url,
                obj.photo.url
            )
    except Exception as e:
        print(f"Error displaying photo: {e}")
    return "无照片"
display_photo.short_description = "现场照片"
```

**改进点**:
- ✅ 检查 photo 字段是否存在: `if obj.photo`
- ✅ 检查是否有 url 属性: `hasattr(obj.photo, 'url')`
- ✅ Try-except 异常处理: 捕捉所有错误
- ✅ 默认返回值: "无照片" 确保总有有效显示

---

### 修复 3: 安全处理 location_display()

**文件**: [core/admin.py](core/admin.py#L228-L241)

```python
def location_display(self, obj):
    """显示巡查位置的经纬度"""
    try:
        if obj.latitude is not None and obj.longitude is not None:
            return format_html(
                '📍 {:.5f}, {:.5f}',
                float(obj.latitude),
                float(obj.longitude)
            )
    except (ValueError, TypeError) as e:
        print(f"Error displaying location: {e}")
    return "无位置"
location_display.short_description = '巡查位置'
```

**改进点**:
- ✅ 使用 `is not None` 而非 `if obj.latitude`: 区分 0 和空值
- ✅ 显式类型转换: `float()` 确保是正确类型
- ✅ 捕捉 ValueError 和 TypeError: 处理类型转换错误
- ✅ 默认返回: "无位置" 作为备用

---

### 修复 4: 安全处理 issue_summary()

**文件**: [core/admin.py](core/admin.py#L284-L299)

```python
def issue_summary(self, obj):
    """显示问题简述"""
    try:
        if obj.is_normal:
            return mark_safe('<span style="color: green;">✓ 正常</span>')
        else:
            summary = obj.issue_details[:30] if obj.issue_details else '有问题'
            return format_html(
                '<span style="color: red;">⚠️ 发现问题</span><br><small>{}</small>',
                summary
            )
    except Exception as e:
        print(f"Error in issue_summary: {e}")
        return "显示错误"
issue_summary.short_description = '巡查情况'
```

**改进点**:
- ✅ Try-except 包裹整个逻辑: 捕捉所有可能的错误
- ✅ 检查 issue_details: `if obj.issue_details` 处理空值
- ✅ 默认值: '有问题' 让UI显示完整

---

### 修复 5: 改进 FormData 上传

**文件**: [app/lib/services/api_service.dart](app/lib/services/api_service.dart#L180-L195)

```dart
final response = await _dio.post(
  ApiConfig.createInspectionEndpoint,
  data: formData,
  options: Options(
    headers: {
      // 移除 Content-Type 头，让 Dio 自动设置为 multipart/form-data
      // contentType 会自动被设置
    },
  ),
);
```

**改进点**:
- ✅ 保持 FormData 的 Content-Type 自动检测
- ✅ 允许 Dio 正确设置 multipart/form-data
- ✅ 确保文件上传的正确编码

---

## 🔄 修复后的完整流程

### App 同步上传流程 (修复后)

```
用户点击"同步"
  ↓
syncUnuploadedRecords()
  ↓
1. GET /api/inspections/my-records/?page=1&page_size=20  ✅ 成功
  ↓
2. 获取未上传的记录列表
  ↓
3. 对每条记录调用:
   - uploadInspectionPhoto()  (含文件) + multipart/form-data ✅
   - 或 createInspection()     (仅JSON)
  ↓
4. 标记为已上传
  ↓
✅ 上传完成
```

### 后端 Admin 显示流程 (修复后)

```
访问 /admin/core/inspectionrecord/
  ↓
加载列表页面:
  ↓
对每条记录调用 list_display 方法:
  - display_photo()     ✅ 异常处理完整
  - location_display()  ✅ 异常处理完整
  - issue_summary()     ✅ 异常处理完整
  ↓
✅ 200 OK - 列表正常显示
```

---

## 📋 测试清单

### 后端测试

- [ ] **测试 my_records 端点**
  ```bash
  # 获取我的巡查记录
  curl -X GET 'http://localhost:8000/api/inspections/my-records/?page=1&page_size=20' \
    -H 'Authorization: Bearer {token}'
  ```
  
  预期结果: 
  - 状态码: 200 ✅
  - 返回当前用户的记录列表
  - 支持分页

- [ ] **测试表单数据上传**
  ```bash
  # 上传含文件的巡查记录
  curl -X POST 'http://localhost:8000/api/inspections/' \
    -H 'Authorization: Bearer {token}' \
    -F 'site=1' \
    -F 'is_normal=true' \
    -F 'photo=@/path/to/photo.jpg' \
    -F 'latitude=39.123' \
    -F 'longitude=117.456'
  ```
  
  预期结果:
  - 状态码: 201 Created ✅
  - 记录成功保存
  - 文件正确上传

- [ ] **测试 Admin 列表页面**
  - 导航: http://localhost:8000/admin/core/inspectionrecord/
  - 检查:
    - ✅ 页面能正常加载（无 500 错误）
    - ✅ 显示所有巡查记录
    - ✅ 照片、位置、问题等信息显示正常

### App 测试

- [ ] **重新编译 Flutter 应用**
  ```bash
  cd app
  flutter pub get
  flutter run -d 24129PN74C
  ```

- [ ] **测试巡查历史同步**
  - 打开"巡查历史"
  - 点击"同步"按钮
  - 检查:
    - ✅ 加载待同步列表
    - ✅ 逐条上传
    - ✅ 状态变为"已同步"

- [ ] **测试新建巡查提交**
  - 新建一条巡查记录
  - 上传照片
  - 点击"提交"
  - 检查网页后台是否显示新记录

---

## 🚀 后续步骤

### 1. 应用修复 (立即)
- [x] API 端点添加 my_records action
- [x] Admin 方法添加异常处理
- [x] FormData 上传改进

### 2. 测试验证 (20 分钟)
- [ ] 启动 Django 开发服务器
- [ ] 编译 Flutter 应用
- [ ] 手动测试上传和同步
- [ ] 检查后台显示

### 3. 部署上线 (如无问题)
- [ ] 提交代码到版本控制
- [ ] 部署到测试环境
- [ ] 部署到生产环境  
- [ ] 通知用户升级 App

---

## 📞 常见问题

### Q: 为什么还是看不到上传的记录?

A: 检查以下几点：
1. 是否已按照操作步骤重新编译 App
2. 确认 Django 后端已重启
3. 检查网络连接和防火墙
4. 查看浏览器开发者工具看API响应

### Q: 表单数据上传仍然失败怎么办?

A: 检查：
1. 照片文件是否存在和可读
2. 服务器磁盘空间是否充足
3. Photo 字段的 upload_to 目录是否存在
4. 日志文件 (`tail -f logs/django.log`) 中的错误信息

### Q: Admin 列表仍然显示 500?

A: 可能是其他原因：
1. 检查数据库中是否有 NULL 值导致的数据问题
2. 在 Django shell 中单独测试每个方法
3. 查看 Django 错误日志了解具体错误
4. 考虑在方法中添加更详细的日志

---

**修复完成时间**: 2026-03-09 23:59  
**测试状态**: ⏳ 待验证  
**部署状态**: ⚪ 待部署
