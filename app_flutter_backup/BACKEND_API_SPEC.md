# 后端 API 集成指南

本文档说明了 Flutter 移动应用需要的后端 API 实现需求。

## API 概览

| 功能 | 方法 | 端点 | 认证 |
|------|------|------|------|
| 用户登录 | POST | `/api/auth/login/` | ❌ |
| 获取用户信息 | GET | `/api/auth/user/` | ✅ |
| 获取附近文物 | GET | `/api/heritages/nearby/` | ✅ |
| 创建巡查记录 | POST | `/api/inspections/create/` | ✅ |
| 获取我的巡查记录 | GET | `/api/inspections/my-records/` | ✅ |
| 获取统计信息 | GET | `/api/inspections/statistics/` | ✅ |

✅ = 需要 Token 认证（请求头: `Authorization: Token <token>`）
❌ = 无需认证

## 1. 认证模块 API

### 1.1 用户登录

**请求**
```http
POST /api/auth/login/
Content-Type: application/json

{
  "username": "inspector01",
  "password": "password123"
}
```

**成功响应 (200 OK)**
```json
{
  "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b",
  "user": {
    "id": 1,
    "username": "inspector01",
    "email": "inspector@example.com",
    "first_name": "张",
    "last_name": "三",
    "is_staff": false,
    "permissions": [
      "view_heritage",
      "add_inspection",
      "view_inspection"
    ],
    "user_group": "看护员",
    "department": "文物保护科"
  }
}
```

**错误响应 (400 Bad Request / 401 Unauthorized)**
```json
{
  "detail": "用户名或密码错误"
}
```

### 1.2 获取当前用户信息

**请求**
```http
GET /api/auth/user/
Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
```

**成功响应 (200 OK)**
```json
{
  "id": 1,
  "username": "inspector01",
  "email": "inspector@example.com",
  "first_name": "张",
  "last_name": "三",
  "is_staff": false,
  "permissions": ["view_heritage", "add_inspection"],
  "user_group": "看护员",
  "department": "文物保护科"
}
```

## 2. 文物点 API

### 2.1 获取附近的文物点

返回指定位置周围范围内的文物点列表，并按距离排序。

**请求**
```http
GET /api/heritages/nearby/?latitude=39.9&longitude=116.4&radius=5.0
Authorization: Token <token>
```

**查询参数**
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| latitude | float | ✅ | 用户纬度 |
| longitude | float | ✅ | 用户经度 |
| radius | float | ❌ | 搜索半径（默认 5.0 km） |

**成功响应 (200 OK)**
```json
[
  {
    "id": 1,
    "name": "明城墙遗址",
    "sip_code": "BJ001",
    "category": "GYZ",
    "level": "GB",
    "address": "北京市朝阳区某处",
    "longitude": 116.4142,
    "latitude": 39.9015,
    "description": "保存完好的古代防御工事遗迹",
    "manager": "北京文物研究所",
    "distance": 2.5
  },
  {
    "id": 2,
    "name": "古建筑群",
    "sip_code": "BJ002",
    "category": "GJZ",
    "level": "SB",
    "address": "北京市东城区某处",
    "longitude": 116.3950,
    "latitude": 39.9042,
    "description": "明清时期的建筑群遗存",
    "manager": "故宫博物院",
    "distance": 4.8
  }
]
```

**错误响应 (400 Bad Request)**
```json
{
  "error": "latitude 和 longitude 是必需的参数"
}
```

## 3. 巡查记录 API

### 3.1 创建/上传巡查记录

支持两种模式：
- 仅上传表单数据（无照片）
- 上传multi-part表单数据（包括照片）

**请求 - 仅表单数据**
```http
POST /api/inspections/create/
Authorization: Token <token>
Content-Type: application/json

{
  "site": 1,
  "is_normal": true,
  "issue_details": "",
  "latitude": 39.9015,
  "longitude": 116.4142
}
```

**请求 - 带照片（multi-part）**
```http
POST /api/inspections/create/
Authorization: Token <token>
Content-Type: multipart/form-data; boundary=----Boundary123

------Boundary123
Content-Disposition: form-data; name="site"

1
------Boundary123
Content-Disposition: form-data; name="is_normal"

true
------Boundary123
Content-Disposition: form-data; name="latitude"

39.9015
------Boundary123
Content-Disposition: form-data; name="longitude"

116.4142
------Boundary123
Content-Disposition: form-data; name="photo"; filename="photo_20260309_103000.jpg"
Content-Type: image/jpeg

<二进制图片数据>
------Boundary123--
```

**请求字段说明**
| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| site | integer | ✅ | 文物点 ID |
| is_normal | boolean | ✅ | 是否正常（true=正常, false=异常） |
| issue_details | string | ❌ | 问题描述（标记异常时填写） |
| latitude | float | ❌ | 巡查时的纬度 |
| longitude | float | ❌ | 巡查时的经度 |
| photo | file | ❌ | 现场照片（JPG/PNG，≤5MB） |

**成功响应 (201 Created)**
```json
{
  "id": 123,
  "site": 1,
  "site_name": "明城墙遗址",
  "inspector": 1,
  "inspector_name": "张三",
  "photo": "/media/inspections/2026/03/photo_abc123.jpg",
  "latitude": 39.9015,
  "longitude": 116.4142,
  "inspect_time": "2026-03-09T10:30:00Z",
  "is_normal": true,
  "issue_details": "",
  "created_at": "2026-03-09T10:32:00Z"
}
```

**错误响应 (400 Bad Request)**
```json
{
  "site": ["不存在的文物点 ID"],
  "photo": ["文件过大，最大为 5MB"]
}
```

### 3.2 获取我的巡查记录

分页返回当前用户的巡查记录。

**请求**
```http
GET /api/inspections/my-records/?page=1&page_size=20
Authorization: Token <token>
```

**查询参数**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | integer | 1 | 页码 |
| page_size | integer | 20 | 每页记录数 |
| site | integer | - | 按文物点过滤（可选） |

**成功响应 (200 OK)**
```json
{
  "count": 50,
  "next": "http://api.example.com/api/inspections/my-records/?page=2",
  "previous": null,
  "results": [
    {
      "id": 123,
      "site": 1,
      "site_name": "明城墙遗址",
      "photo": "/media/inspections/2026/03/photo_abc123.jpg",
      "latitude": 39.9015,
      "longitude": 116.4142,
      "inspect_time": "2026-03-09T10:30:00Z",
      "is_normal": true,
      "issue_details": "",
      "created_at": "2026-03-09T10:32:00Z"
    },
    {
      "id": 122,
      "site": 2,
      "site_name": "古建筑群",
      "photo": "/media/inspections/2026/03/photo_def456.jpg",
      "latitude": 39.9042,
      "longitude": 116.3950,
      "inspect_time": "2026-03-08T14:15:00Z",
      "is_normal": false,
      "issue_details": "东墙出现裂缝，需要修缮",
      "created_at": "2026-03-08T14:20:00Z"
    }
  ]
}
```

### 3.3 获取统计信息

**请求**
```http
GET /api/inspections/statistics/
Authorization: Token <token>
```

**成功响应 (200 OK)**
```json
{
  "total_inspections": 150,
  "today_inspections": 8,
  "this_month_inspections": 42,
  "normal_count": 145,
  "abnormal_count": 5,
  "last_inspection": "2026-03-09T14:30:00Z",
  "coverage_rate": 0.85
}
```

## 4. 认证机制

### Token 认证

所有需要认证的端点都需要在请求头中包含 Token：

```http
Authorization: Token <token>
```

例如：
```http
GET /api/heritages/nearby/?latitude=39.9&longitude=116.4
Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
```

### Token 格式

应用使用 Django Token 认证机制。Token 应该：
- 由 40 个十六进制字符组成
- 唯一标识一个用户的会话
- 登录时返回，客户端需要持久保存

### 错误响应

**401 Unauthorized - Token 过期或无效**
```json
{
  "detail": "Invalid token."
}
```

**403 Forbidden - 无权限**
```json
{
  "detail": "You do not have permission to perform this action."
}
```

## 5. 数据验证和错误处理

### 输入验证

所有 API 端点都应进行适当的输入验证：

- **latitude / longitude**: 应为有效的浮点数，在合理范围内 (-90 to 90 for latitude, -180 to 180 for longitude)
- **radius**: 应为正数，建议上限 50 km
- **site**: 应为存在的文物点 ID
- **photo**: 文件大小应 ≤ 5MB，格式应为 JPG 或 PNG

### 错误响应格式

所有错误响应应遵循统一格式：

```json
{
  "detail": "错误信息描述",
  "error_code": "ERROR_CODE"
}
```

或者对于验证错误（400）：

```json
{
  "field_name": ["错误信息 1", "错误信息 2"],
  "another_field": ["错误信息 3"]
}
```

## 6. 实现建议

### Django REST Framework 示例

```python
from rest_framework import views, viewsets, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import User
from core.models import HeritageSite, InspectionRecord
from core.serializers import HeritageSiteSerializer, InspectionRecordSerializer

# 登录视图
from rest_framework.authtoken.views import obtain_auth_token

# 从 url 配置中
path('api-auth-token/', obtain_auth_token)

# 文物点视图
class HeritageViewSet(viewsets.ModelViewSet):
    queryset = HeritageSite.objects.all()
    serializer_class = HeritageSiteSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def nearby(self, request):
        latitude = request.query_params.get('latitude')
        longitude = request.query_params.get('longitude')
        radius = float(request.query_params.get('radius', 5.0))
        
        # 实现距离计算逻辑
        # 返回附近的文物点
        ...

# 巡查记录视图
class InspectionViewSet(viewsets.ModelViewSet):
    serializer_class = InspectionRecordSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)
    
    def get_queryset(self):
        return InspectionRecord.objects.filter(inspector=self.request.user)
    
    def create(self, request):
        # 处理照片上传和巡查记录创建
        ...
```

## 7. 测试 API

### 使用 curl 测试

**登录**
```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"inspector01","password":"password123"}'
```

**获取附近文物**
```bash
curl -X GET "http://localhost:8000/api/heritages/nearby/?latitude=39.9&longitude=116.4&radius=5" \
  -H "Authorization: Token <token>"
```

**上传巡查记录**
```bash
curl -X POST http://localhost:8000/api/inspections/create/ \
  -H "Authorization: Token <token>" \
  -F "site=1" \
  -F "is_normal=true" \
  -F "latitude=39.9" \
  -F "longitude=116.4" \
  -F "photo=@/path/to/photo.jpg"
```

## 8. 性能和可靠性要求

- **响应时间**: 建议 ≤ 1 秒（不含网络延迟）
- **并发连接**: 应支持至少 100+ 并发用户
- **照片上传**: 建议支持断点续传或分块上传
- **数据库**: 应建立索引加快位置查询（latitude, longitude）
- **缓存**: 建议缓存文物点信息，减少数据库查询

## 9. 安全建议

- 所有 API 端点都应强制 HTTPS
- Token 应实现过期机制（建议 7 天）
- 限制 API 请求速率防止滥用
- 照片上传应验证文件类型和大小
- 位置数据应基于权限限制返回
- 用户只能访问自己的巡查记录

---

文档版本: 1.0
更新时间: 2026 年 3 月 9 日
