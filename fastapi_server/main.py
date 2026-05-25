from datetime import datetime
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import math
import shutil
import sqlite3
import sys
import time
from typing import Any
from urllib.parse import quote
import uuid
import io

# 1. 获取当前 fastapi_server 的父目录（即 heritage_system 根目录）
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)

# 2. 将根目录加入系统路径
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 3. 设置 Django 的环境变量（确保名称与你 Django 项目一致）
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'heritage_system.settings')

import django
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from docx import Document
from docx.shared import Mm, Pt
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from PIL import Image as PILImage




BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "heritage_system.settings")
django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.db import models
from core.models import HeritageSite, InspectionRecord, ProjectAudit  # type: ignore[import]
from core.models import ImmovableHeritage, HeritagePhoto            # type: ignore[import]
from core.utils_watermark import add_heritage_watermark             # type: ignore[import]


DB_PATH = Path(settings.DATABASES["default"]["NAME"])
MEDIA_ROOT = Path(settings.MEDIA_ROOT)


app = FastAPI(title="Heritage Patrol FastAPI", version="1.0.0")
security = HTTPBearer(auto_error=False)
User = get_user_model()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://beichenhome.top:9081", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


def get_conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise HTTPException(status_code=500, detail="Django database file not found")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


def b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("utf-8"))


def get_user_role(user: Any) -> str:
    if user.is_superuser or user.groups.filter(name="超级管理员").exists():
        return "超级管理员"
    if user.groups.filter(name="管理员").exists():
        return "管理员"
    if user.groups.filter(name="管理员用户组").exists():
        return "管理员用户组"
    if user.groups.filter(name="文物看护员").exists():
        return "文物看护员"
    return "普通用户"


def has_management_access(user: Any) -> bool:
    role = get_user_role(user)
    return role in {"超级管理员", "管理员", "管理员用户组"}


def can_modify_core_data(user: Any) -> bool:
    role = get_user_role(user)
    return role in {"超级管理员", "管理员"}


def serialize_user(user: Any) -> dict:
    groups = list(user.groups.values_list("name", flat=True))
    role = get_user_role(user)
    is_admin = role in {"超级管理员", "管理员", "管理员用户组"}
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.first_name or user.username,
        "role": role,
        "groups": groups,
        "is_superuser": user.is_superuser,
        "is_admin": is_admin,
        "permissions": {
            "can_patrol": role in {"超级管理员", "管理员", "文物看护员"},
            "can_view_all_heritages": is_admin,
            "can_manage_projects": is_admin,
            "can_use_kml_overlay": is_admin,
            "can_modify_core_data": can_modify_core_data(user),
        },
    }


def create_token(user: Any, expires_in: int = 60 * 60 * 12) -> str:
    payload = {
        "user_id": user.id,
        "username": user.username,
        "exp": int(time.time()) + expires_in,
    }
    payload_str = b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_str}.{signature}"


def parse_token(token: str) -> dict:
    try:
        payload_str, signature = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token format") from exc

    expected_signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=401, detail="Invalid token signature")

    payload = json.loads(b64url_decode(payload_str).decode("utf-8"))
    if payload.get("exp", 0) < int(time.time()):
        raise HTTPException(status_code=401, detail="Token expired")
    return payload


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> Any:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication required")
    payload = parse_token(credentials.credentials)
    user = User.objects.filter(id=payload.get("user_id"), is_active=True).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_admin(current_user: Any = Depends(get_current_user)) -> Any:
    if not has_management_access(current_user):
        raise HTTPException(status_code=403, detail="Admin permission required")
    return current_user


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ProjectUpdateRequest(BaseModel):
    project_name: str
    project_unit: str = ""
    workflow_status: str
    construction_content: str = ""
    project_scale: str = ""
    project_coordinates: str = ""
    project_lon: float | None = None
    project_lat: float | None = None
    related_site_id: int | None = None
    survey_conclusion: str = ""
    remarks: str = ""


def serialize_project(project: ProjectAudit) -> dict:
    return {
        "id": project.id,
        "project_name": project.project_name,
        "project_unit": project.project_unit,
        "workflow_status": project.workflow_status,
        "workflow_status_display": project.get_workflow_status_display(),
        "construction_content": project.construction_content,
        "project_scale": project.project_scale,
        "project_coordinates": project.project_coordinates,
        "project_lon": project.project_lon,
        "project_lat": project.project_lat,
        "related_site_id": project.related_site_id,
        "related_site_name": project.related_site.name if project.related_site else "",
        "survey_conclusion": project.survey_conclusion,
        "remarks": project.remarks,
        "is_in_protection_zone": project.is_in_protection_zone,
        "is_in_control_zone": project.is_in_control_zone,
        "received_date": project.received_date.strftime("%Y-%m-%d %H:%M") if project.received_date else "",
    }


def serialize_heritage(site: HeritageSite) -> dict:
    return {
        "id": site.id,
        "name": site.name,
        "sip_code": site.sip_code,
        "category": site.get_category_display(),
        "level": site.get_level_display(),
        "address": site.address,
        "longitude": site.longitude,
        "latitude": site.latitude,
        "manager": site.manager,
    }


def normalize_heritage_category(category_value: str) -> str:
    category_value = (category_value or "").strip()
    if not category_value:
        return ""

    category_alias_map = {
        'GJZ': 'GJZ',
        '古建筑': 'GJZ',
        'GMZ': 'GMZ',
        '古墓葬': 'GMZ',
        'GYZ': 'GYZ',
        '古文化遗址': 'GYZ',
        '古遗址': 'GYZ',
        'SKT': 'SKT',
        '石窟寺及石刻': 'SKT',
        '石刻': 'SKT',
        'JDJW': 'JDJW',
        '近现代重要史迹及代表性建筑': 'JDJW',
        'QT': 'QT',
        '其他': 'QT',
    }

    return category_alias_map.get(category_value, category_value)


def serialize_inspection(record: InspectionRecord) -> dict:
    base_url = os.environ.get("DJANGO_WEB_BASE_URL", "https://beichenhome.top:9081").rstrip("/")
    photo_url = ""
    if record.photo:
        photo_url = f"{base_url}/media/{str(record.photo).lstrip('/')}"
    return {
        "id": record.id,
        "site_id": record.site_id,
        "site_name": record.site.name if record.site else "",
        "inspect_time": record.inspect_time.strftime("%Y-%m-%d %H:%M") if record.inspect_time else "",
        "is_normal": record.is_normal,
        "issue_details": record.issue_details or "",
        "latitude": record.latitude,
        "longitude": record.longitude,
        "photo_url": photo_url,
    }


@app.get("/")
def root() -> dict:
    return {"message": "FastAPI is running"}


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> dict:
    user = User.objects.filter(username=payload.username, is_active=True).first()
    if user is None or not check_password(payload.password, user.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {
        "token": create_token(user),
        "user": serialize_user(user),
    }


@app.get("/api/auth/me")
def get_me(current_user: Any = Depends(get_current_user)) -> dict:
    return {"user": serialize_user(current_user)}


@app.post("/api/auth/change-password")
def change_password(payload: ChangePasswordRequest, current_user: Any = Depends(get_current_user)) -> dict:
    if not check_password(payload.current_password, current_user.password):
        raise HTTPException(status_code=400, detail="当前密码错误")
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码长度不能少于6位")
    if check_password(payload.new_password, current_user.password):
        raise HTTPException(status_code=400, detail="新密码不能与旧密码相同")

    current_user.set_password(payload.new_password)
    current_user.save(update_fields=["password"])
    return {"message": "password_updated"}


@app.get("/api/dashboard/realtime-stats")
def get_realtime_dashboard_stats(current_user: Any = Depends(get_current_user)) -> dict:
    total_sites = HeritageSite.objects.count()
    total_inspections = InspectionRecord.objects.count()
    my_inspections = InspectionRecord.objects.filter(inspector=current_user).count()
    abnormal_count = InspectionRecord.objects.filter(is_normal=False).count()

    level_rows = (
        HeritageSite.objects.values("level")
        .order_by("level")
        .annotate(count=models.Count("id"))
    )
    category_rows = (
        HeritageSite.objects.values("category")
        .order_by("category")
        .annotate(count=models.Count("id"))
    )

    level_map = dict(HeritageSite.LEVEL_CHOICES)
    category_map = dict(HeritageSite.CATEGORY_CHOICES)

    level_stats = [
        {
            "key": row["level"],
            "name": level_map.get(row["level"], row["level"]),
            "count": row["count"],
        }
        for row in level_rows
    ]

    category_stats = [
        {
            "key": row["category"],
            "name": category_map.get(row["category"], row["category"]),
            "count": row["count"],
        }
        for row in category_rows
    ]

    return {
        "county": "鄯善县",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "overview": {
            "total_sites": total_sites,
            "total_inspections": total_inspections,
            "my_inspections": my_inspections,
            "abnormal_count": abnormal_count,
        },
        "level_stats": level_stats,
        "category_stats": category_stats,
    }


@app.get("/api/heritages/nearby")
def get_nearest_heritage(
    latitude: float,
    longitude: float,
    current_user: Any = Depends(get_current_user),
) -> dict:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, name, address, longitude, latitude FROM core_heritagesite"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="No heritage sites found")

    nearest = None
    min_distance = None

    for row in rows:
        if row["latitude"] is None or row["longitude"] is None:
            continue
        distance = haversine_km(latitude, longitude, row["latitude"], row["longitude"])
        if min_distance is None or distance < min_distance:
            min_distance = distance
            nearest = row

    if nearest is None:
        raise HTTPException(status_code=404, detail="No mappable heritage sites found")

    return {
        "id": nearest["id"],
        "name": nearest["name"],
        "address": nearest["address"],
        "site_latitude": nearest["latitude"],
        "site_longitude": nearest["longitude"],
        "distance": round(float(min_distance), 3),
    }


@app.get("/api/heritages/search")
def search_heritages(
    q: str = Query("", max_length=50),
    limit: int = Query(20, ge=1, le=100),
    current_user: Any = Depends(get_current_user),
) -> dict:
    role = get_user_role(current_user)
    if role not in {"超级管理员", "管理员", "文物看护员"}:
        raise HTTPException(status_code=403, detail="No patrol permission")

    keyword = q.strip()
    queryset = HeritageSite.objects.all()
    if keyword:
        queryset = queryset.filter(
            models.Q(name__icontains=keyword)
            | models.Q(sip_code__icontains=keyword)
            | models.Q(address__icontains=keyword)
        )

    sites = queryset.order_by("name")[:limit]
    return {
        "items": [serialize_heritage(site) for site in sites],
        "keyword": keyword,
        "limit": limit,
    }


@app.post("/api/inspections/upload", status_code=201)
def upload_inspection(
    site_id: int = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    is_normal: bool = Form(True),
    issue_details: str = Form(""),
    photo: UploadFile = File(...),
    current_user: Any = Depends(get_current_user),
) -> dict:
    role = get_user_role(current_user)
    if role == "管理员用户组":
        raise HTTPException(status_code=403, detail="管理员用户组不允许新增巡查记录")
    if role not in {"超级管理员", "管理员", "文物看护员"}:
        raise HTTPException(status_code=403, detail="No patrol permission")

    site = HeritageSite.objects.filter(id=site_id).first()
    if site is None:
        raise HTTPException(status_code=404, detail="Heritage site not found")

    issue_details = (issue_details or "").strip()
    if not is_normal and not issue_details:
        raise HTTPException(status_code=400, detail="存在问题时，问题说明不能为空")

    now = datetime.now()
    rel_dir = Path("inspections") / now.strftime("%Y") / now.strftime("%m")
    target_dir = MEDIA_ROOT / rel_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(photo.filename or "patrol.jpg").suffix or ".jpg"
    filename = f"{now.strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{suffix}"
    file_path = target_dir / filename

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(photo.file, buffer)

    photo_rel_path = str((rel_dir / filename).as_posix())
    record = InspectionRecord.objects.create(
        site=site,
        inspector=current_user,
        is_normal=is_normal,
        issue_details=issue_details,
        photo=photo_rel_path,
        latitude=latitude,
        longitude=longitude,
    )

    return {
        "id": record.id,
        "site_id": site_id,
        "inspector_id": current_user.id,
        "photo": f"/media/{photo_rel_path}",
        "message": "Inspection uploaded successfully",
    }


@app.get("/api/inspections/mine")
def list_my_inspections(current_user: Any = Depends(get_current_user)) -> dict:
    role = get_user_role(current_user)
    if role not in {"超级管理员", "管理员", "文物看护员"}:
        raise HTTPException(status_code=403, detail="No patrol permission")

    records = (
        InspectionRecord.objects.select_related("site")
        .filter(inspector=current_user)
        .order_by("-inspect_time")[:100]
    )
    return {"items": [serialize_inspection(record) for record in records]}


@app.get("/api/admin/heritages")
def list_all_heritages(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    q: str = Query(""),
    category: str = Query(""),
    current_user: Any = Depends(require_admin),
) -> dict:
    queryset = HeritageSite.objects.all()

    keyword = (q or "").strip()
    if keyword:
        queryset = queryset.filter(
            models.Q(name__icontains=keyword)
            | models.Q(sip_code__icontains=keyword)
            | models.Q(address__icontains=keyword)
            | models.Q(category__icontains=keyword)
            | models.Q(level__icontains=keyword)
        )

    category_value = normalize_heritage_category(category)
    if category_value:
        queryset = queryset.filter(category=category_value)

    queryset = queryset.order_by("name")
    total = queryset.count()
    offset = (page - 1) * page_size
    sites = queryset[offset : offset + page_size]

    total_pages = (total + page_size - 1) // page_size if total else 1

    return {
        "items": [serialize_heritage(site) for site in sites],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
        },
    }


@app.get("/api/admin/projects")
def list_projects(current_user: Any = Depends(require_admin)) -> dict:
    projects = ProjectAudit.objects.select_related("related_site").all().order_by("-received_date")[:200]
    return {"items": [serialize_project(project) for project in projects]}


@app.put("/api/admin/projects/{project_id}")
def update_project(
    project_id: int,
    payload: ProjectUpdateRequest,
    current_user: Any = Depends(require_admin),
) -> dict:
    project = ProjectAudit.objects.filter(id=project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    related_site = None
    if payload.related_site_id:
        related_site = HeritageSite.objects.filter(id=payload.related_site_id).first()
        if related_site is None:
            raise HTTPException(status_code=404, detail="Related heritage site not found")

    project.project_name = payload.project_name
    project.project_unit = payload.project_unit
    project.workflow_status = payload.workflow_status
    project.construction_content = payload.construction_content
    project.project_scale = payload.project_scale
    project.project_coordinates = payload.project_coordinates
    project.project_lon = payload.project_lon
    project.project_lat = payload.project_lat
    project.related_site = related_site
    project.survey_conclusion = payload.survey_conclusion
    project.remarks = payload.remarks
    project.save()

    return {
        "message": "Project updated successfully",
        "item": serialize_project(project),
    }


@app.get("/api/admin/kml-overlay-entry")
def kml_overlay_entry(current_user: Any = Depends(require_admin)) -> dict:
    base_url = os.environ.get("DJANGO_WEB_BASE_URL", "https://beichenhome.top:9081")
    token = create_token(current_user, expires_in=60 * 10)
    target = quote("/admin/kml-overlay-check/", safe="/")
    return {
        "url": f"{base_url.rstrip('/')}/mobile/kml-entry/?token={quote(token)}&next={target}",
        "note": "该功能复用现有 Django 网页工具，App 将自动桥接登录后再打开KML叠加检查。",
    }


@app.get("/api/admin/collect-entry")
def collect_entry(current_user: Any = Depends(require_admin)) -> dict:
    base_url = os.environ.get("DJANGO_WEB_BASE_URL", "https://beichenhome.top:9081")
    token = create_token(current_user, expires_in=60 * 10)
    target = quote("/mobile/collect/", safe="/")
    return {
        "url": f"{base_url.rstrip('/')}/mobile/collect-entry/?token={quote(token)}&next={target}",
        "note": "该功能复用现有 Django 网页工具，App 将自动桥接登录后再打开不可移动文物采集页。",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 不可移动文物现场采集 API（四普）
# ─────────────────────────────────────────────────────────────────────────────

class CollectCreateRequest(BaseModel):
    """第一步：提交文字表单，创建 ImmovableHeritage 记录"""
    survey_code: str = ""
    name: str
    former_name: str = ""
    era: str
    category: str
    heritage_type: str = ""
    province: str = ""
    city: str = ""
    county: str = ""
    township: str = ""
    village: str = ""
    address: str = ""
    coordinate_system: str = "CGCS2000"
    longitude: float
    latitude: float
    altitude: float | None = None
    area: float | None = None
    protection_level: str = "DS"
    ownership: str = "state"
    preservation_status: str = "一般"
    damage_cause: str = ""
    threat_factors: str = ""
    description: str = ""


@app.get("/api/collect/form-meta")
def collect_form_meta(current_user: Any = Depends(get_current_user)) -> dict:
    """
    返回采集表单所需的全部选项（分类、保护级别、权属、保存现状）。
    App 启动表单页时调用，避免硬编码选项。
    """
    return {
        "category_choices": [
            {"value": v, "label": l} for v, l in ImmovableHeritage.CATEGORY_CHOICES
        ],
        "protection_level_choices": [
            {"value": v, "label": l} for v, l in ImmovableHeritage.PROTECTION_LEVEL_CHOICES
        ],
        "ownership_choices": [
            {"value": v, "label": l} for v, l in ImmovableHeritage.OWNERSHIP_CHOICES
        ],
        "preservation_status_choices": [
            {"value": v, "label": l} for v, l in ImmovableHeritage.PRESERVATION_STATUS_CHOICES
        ],
        "collect_unit": os.environ.get("HERITAGE_COLLECT_UNIT", "文物管理部门"),
    }


@app.post("/api/collect/create", status_code=201)
def collect_create(
    payload: CollectCreateRequest,
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    第一步：接收文字表单，创建 ImmovableHeritage 记录并返回 heritage_id。
    照片通过 /api/collect/photos/{heritage_id} 单独上传。

    权限：任意已登录用户均可采集。
    """
    from decimal import Decimal, InvalidOperation

    if not can_modify_core_data(current_user):
        raise HTTPException(status_code=403, detail="管理员用户组仅支持采集数据查看，不允许创建记录")

    # ── 采集编号唯一性（手工填写时）──────────────────────────
    manual_code = (payload.survey_code or "").strip()
    if manual_code and ImmovableHeritage.objects.filter(survey_code=manual_code).exists():
        raise HTTPException(status_code=409, detail="该采集编号已存在，请确认后重新输入")

    # ── 经纬度范围校验 ──────────────────────────────────────
    if not (-180 <= payload.longitude <= 180):
        raise HTTPException(status_code=400, detail="经度须在 -180 ~ 180 之间")
    if not (-90 <= payload.latitude <= 90):
        raise HTTPException(status_code=400, detail="纬度须在 -90 ~ 90 之间")

    from django.utils import timezone

    now = timezone.now()
    try:
        heritage = ImmovableHeritage.objects.create(
            survey_code=manual_code,
            former_name=payload.former_name.strip(),
            name=payload.name.strip(),
            era=payload.era.strip(),
            category=payload.category,
            heritage_type=payload.heritage_type.strip(),
            province=payload.province.strip(),
            city=payload.city.strip(),
            county=payload.county.strip(),
            township=payload.township.strip(),
            village=payload.village.strip(),
            address=payload.address.strip(),
            coordinate_system=payload.coordinate_system,
            longitude=Decimal(str(payload.longitude)),
            latitude=Decimal(str(payload.latitude)),
            altitude=Decimal(str(payload.altitude)) if payload.altitude is not None else None,
            area=Decimal(str(payload.area)) if payload.area is not None else None,
            protection_level=payload.protection_level,
            ownership=payload.ownership,
            preservation_status=payload.preservation_status,
            damage_cause=payload.damage_cause.strip(),
            threat_factors=payload.threat_factors.strip(),
            description=payload.description.strip(),
            collector=current_user,
            collected_at=now,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"创建记录失败：{exc}") from exc

    return {
        "heritage_id": heritage.id,
        "survey_code": heritage.survey_code,
        "name": heritage.name,
        "message": f"文物「{heritage.name}」已登记，请继续上传现场照片",
    }


@app.post("/api/collect/photos/{heritage_id}", status_code=201)
def collect_upload_photo(
    heritage_id: int,
    photo: UploadFile = File(...),
    photo_type: str = Form("overview"),
    is_cover: bool = Form(False),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    第二步：为已创建的 ImmovableHeritage 记录上传一张现场照片。
    服务端自动合成 Pillow 水印（文物名称 / 经纬度(度分秒) / 采集时间 / 采集单位）
    后保存为 HeritagePhoto。

    App 端对每张照片调用一次此接口（顺序上传）。
    """
    import io as _io
    from django.core.files.base import ContentFile
    from django.utils import timezone

    heritage = ImmovableHeritage.objects.filter(id=heritage_id).first()
    if heritage is None:
        raise HTTPException(status_code=404, detail="文物记录不存在")

    if not can_modify_core_data(current_user):
        raise HTTPException(status_code=403, detail="管理员用户组仅支持采集数据查看，不允许上传照片")

    # 权限：只有采集人本人或管理员可上传
    role = get_user_role(current_user)
    if heritage.collector_id != current_user.id and role not in {"超级管理员", "管理员"}:
        raise HTTPException(status_code=403, detail="只有采集人本人或管理员可上传照片")

    # 文件类型检查
    content_type = (photo.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件（JPEG / PNG）")

    raw_bytes = photo.file.read()
    if len(raw_bytes) > 30 * 1024 * 1024:          # 30 MB 上限
        raise HTTPException(status_code=413, detail="单张照片不得超过 30 MB")

    collect_unit = os.environ.get("HERITAGE_COLLECT_UNIT", "文物管理部门")
    collected_at = heritage.collected_at or timezone.now()

    try:
        watermarked = add_heritage_watermark(
            image_source=_io.BytesIO(raw_bytes),
            heritage_name=heritage.name,
            collected_at=collected_at,
            longitude=float(heritage.longitude),
            latitude=float(heritage.latitude),
            collect_unit=collect_unit,
        )
        buf = _io.BytesIO()
        watermarked.save(buf, format="JPEG", quality=88, optimize=True)
        buf.seek(0)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"水印合成失败：{exc}") from exc

    now = timezone.now()
    hp = HeritagePhoto(
        heritage=heritage,
        photo_type=photo_type if photo_type in dict(HeritagePhoto.PHOTO_TYPE_CHOICES) else "overview",
        is_cover=is_cover,
        shot_at=collected_at,
        shot_longitude=heritage.longitude,
        shot_latitude=heritage.latitude,
        uploaded_by=current_user,
        caption=f"现场采集照片（{current_user.first_name or current_user.username}）",
    )
    filename = f"collect_{heritage_id}_{now.strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}.jpg"
    hp.image.save(filename, ContentFile(buf.read()), save=True)

    base_url = os.environ.get("DJANGO_WEB_BASE_URL", "https://beichenhome.top:9081").rstrip("/")
    return {
        "photo_id": hp.id,
        "photo_url": f"{base_url}/media/{str(hp.image)}",
        "is_cover": hp.is_cover,
        "message": "照片上传并加水印成功",
    }


@app.get("/api/collect/my-records")
def collect_my_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """返回当前用户采集的文物记录（分页），供 App 端"我的采集"列表使用。"""
    base_url = os.environ.get("DJANGO_WEB_BASE_URL", "https://beichenhome.top:9081").rstrip("/")

    qs = (
        ImmovableHeritage.objects
        .filter(collector=current_user)
        .prefetch_related("photos")
        .order_by("-collected_at")
    )
    total = qs.count()
    offset = (page - 1) * page_size
    records = qs[offset: offset + page_size]

    items = []
    for h in records:
        cover = h.photos.filter(is_cover=True).first() or h.photos.first()
        items.append({
            "id": h.id,
            "survey_code": h.survey_code,
            "name": h.name,
            "era": h.era,
            "category": h.get_category_display(),
            "address": h.address,
            "longitude": float(h.longitude),
            "latitude": float(h.latitude),
            "preservation_status": h.preservation_status,
            "protection_level": h.get_protection_level_display(),
            "collected_at": h.collected_at.strftime("%Y-%m-%d %H:%M") if h.collected_at else "",
            "photo_count": h.photos.count(),
            "cover_url": f"{base_url}/media/{str(cover.image)}" if cover else "",
        })

    return {
        "items": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size if total else 1,
        },
    }


def _set_cell_text_docx(cell, text, *, bold=False, align=WD_PARAGRAPH_ALIGNMENT.LEFT, font_size=14):
    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run("" if text is None else str(text))
    run.bold = bold
    run.font.size = Pt(font_size)
    run.font.name = "宋体"


def _set_table_widths_docx(table, widths_mm):
    for row in table.rows:
        for idx, width in enumerate(widths_mm):
            row.cells[idx].width = Mm(width)


def _decimal_to_dms_docx(decimal_deg, is_longitude: bool) -> str:
    try:
        val = float(decimal_deg)
    except (TypeError, ValueError):
        return "——"

    direction = "东经" if is_longitude and val >= 0 else "西经" if is_longitude else "北纬" if val >= 0 else "南纬"
    val = abs(val)
    deg = int(val)
    minutes_float = (val - deg) * 60
    minute = int(minutes_float)
    second = (minutes_float - minute) * 60
    return f"{direction} {deg}°{minute:02d}′{second:05.2f}″"


def _scaled_photo_size_mm_docx(img_bytes, max_w_mm=68.0, max_h_mm=50.0):
    with PILImage.open(io.BytesIO(img_bytes)) as image:
        px_w, px_h = image.size
    if px_w <= 0 or px_h <= 0:
        return max_w_mm, max_h_mm

    ratio = px_w / px_h
    width_mm = max_w_mm
    height_mm = width_mm / ratio
    if height_mm > max_h_mm:
        height_mm = max_h_mm
        width_mm = height_mm * ratio
    return width_mm, height_mm


def _insert_photos_docx(cell, photos):
    cell.text = ""
    if not photos:
        _set_cell_text_docx(cell, "暂无现场照片", align=WD_PARAGRAPH_ALIGNMENT.CENTER)
        return

    ordered = sorted(photos, key=lambda p: (not p.is_cover, p.uploaded_at or datetime.min))
    selected = ordered[:3]
    for index, photo in enumerate(selected):
        try:
            with photo.image.open("rb") as f:
                img_bytes = f.read()
        except Exception:
            p = cell.add_paragraph()
            p.add_run(f"照片{index + 1}读取失败")
            continue

        width_mm, height_mm = _scaled_photo_size_mm_docx(img_bytes)
        p_img = cell.add_paragraph()
        p_img.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        p_img.add_run().add_picture(io.BytesIO(img_bytes), width=Mm(width_mm), height=Mm(height_mm))

        p_caption = cell.add_paragraph()
        p_caption.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        caption = f"图{index + 1}  {photo.get_photo_type_display()}"
        if photo.caption:
            caption += f"：{photo.caption}"
        cap_run = p_caption.add_run(caption)
        cap_run.font.size = Pt(14)
        cap_run.font.name = "宋体"


@app.get("/api/collect/export-docx/{heritage_id}")
def collect_export_docx(
    heritage_id: int,
    current_user: Any = Depends(get_current_user),
):
    """导出当前记录的不可移动文物采集登记表 DOCX（Bearer 鉴权，适配 UniApp 一键下载）。"""
    heritage = ImmovableHeritage.objects.filter(id=heritage_id).prefetch_related("photos").select_related(
        "collector", "reviewer"
    ).first()
    if heritage is None:
        raise HTTPException(status_code=404, detail="文物记录不存在")

    role = get_user_role(current_user)
    if heritage.collector_id != current_user.id and role not in {"超级管理员", "管理员"}:
        raise HTTPException(status_code=403, detail="无权导出该记录")

    document = Document()
    section = document.sections[0]
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.left_margin = Mm(25.4)
    section.right_margin = Mm(25.4)
    section.top_margin = Mm(25.4)
    section.bottom_margin = Mm(25.4)

    p_title = document.add_paragraph()
    p_title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    title_run = p_title.add_run("鄯善县不可移动文物采集登记表")
    title_run.bold = True
    title_run.font.size = Pt(22)
    title_run.font.name = "黑体"

    p_code = document.add_paragraph()
    p_code.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    code_run = p_code.add_run(f"采集编号：{heritage.survey_code}")
    code_run.bold = True
    code_run.font.size = Pt(14)
    code_run.font.name = "宋体"

    table = document.add_table(rows=17, cols=8)
    table.style = "Table Grid"
    _set_table_widths_docx(table, [18, 24, 14, 24, 14, 24, 14, 27])

    _set_cell_text_docx(table.cell(0, 0).merge(table.cell(0, 7)), "一、基本信息", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(1, 0), "名称", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(1, 1).merge(table.cell(1, 3)), heritage.name)
    _set_cell_text_docx(table.cell(1, 4), "曾用名/别名", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(1, 5).merge(table.cell(1, 7)), heritage.former_name or "——")

    _set_cell_text_docx(table.cell(2, 0), "时代", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(2, 1), heritage.era)
    _set_cell_text_docx(table.cell(2, 2), "类别", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(2, 3), heritage.get_category_display())
    _set_cell_text_docx(table.cell(2, 4), "类型", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(2, 5).merge(table.cell(2, 7)), heritage.heritage_type or "——")

    _set_cell_text_docx(table.cell(3, 0).merge(table.cell(3, 7)), "二、地理位置", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(4, 0), "省/自治区", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(4, 1), heritage.province or "——")
    _set_cell_text_docx(table.cell(4, 2), "市/州", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(4, 3), heritage.city or "——")
    _set_cell_text_docx(table.cell(4, 4), "县/区", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(4, 5).merge(table.cell(4, 7)), heritage.county or "——")

    _set_cell_text_docx(table.cell(5, 0), "乡镇/街道", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(5, 1).merge(table.cell(5, 3)), heritage.township or "——")
    _set_cell_text_docx(table.cell(5, 4), "村/社区", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(5, 5).merge(table.cell(5, 7)), heritage.village or "——")

    _set_cell_text_docx(table.cell(6, 0), "详细地址", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(6, 1).merge(table.cell(6, 7)), heritage.address or "——")

    _set_cell_text_docx(table.cell(7, 0), "坐标系", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(7, 1), heritage.get_coordinate_system_display())
    _set_cell_text_docx(table.cell(7, 2), "经度", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(7, 3), f"{heritage.longitude:.8f}", font_size=14)
    _set_cell_text_docx(table.cell(7, 4), "纬度", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(7, 5), f"{heritage.latitude:.8f}", font_size=14)
    _set_cell_text_docx(table.cell(7, 6), "海拔(m)", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(7, 7), f"{heritage.altitude:.2f}" if heritage.altitude is not None else "——", font_size=14)

    _set_cell_text_docx(table.cell(8, 0), "占地面积", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(8, 1).merge(table.cell(8, 3)), f"{heritage.area:.2f} 平方米" if heritage.area else "——")
    _set_cell_text_docx(table.cell(8, 4), "经度(度分秒)", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER, font_size=14)
    _set_cell_text_docx(table.cell(8, 5), _decimal_to_dms_docx(heritage.longitude, True), font_size=14)
    _set_cell_text_docx(table.cell(8, 6), "纬度(度分秒)", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER, font_size=14)
    _set_cell_text_docx(table.cell(8, 7), _decimal_to_dms_docx(heritage.latitude, False), font_size=14)

    _set_cell_text_docx(table.cell(9, 0).merge(table.cell(9, 7)), "三、现状与保护", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(10, 0), "保存现状", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(10, 1), heritage.preservation_status)
    _set_cell_text_docx(table.cell(10, 2), "权属", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(10, 3), heritage.get_ownership_display())
    _set_cell_text_docx(table.cell(10, 4), "保护级别", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(10, 5).merge(table.cell(10, 7)), heritage.get_protection_level_display())

    _set_cell_text_docx(table.cell(11, 0), "破坏原因", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(11, 1).merge(table.cell(11, 3)), heritage.damage_cause or "无")
    _set_cell_text_docx(table.cell(11, 4), "威胁因素", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(11, 5).merge(table.cell(11, 7)), heritage.threat_factors or "无")

    _set_cell_text_docx(table.cell(12, 0).merge(table.cell(12, 7)), "四、文物简介", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(13, 0).merge(table.cell(13, 7)), heritage.description or "（暂无简介）")

    _set_cell_text_docx(table.cell(14, 0).merge(table.cell(14, 7)), "五、照片说明（现场采集照片）", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _set_cell_text_docx(table.cell(15, 0).merge(table.cell(16, 1)), "照片说明", bold=True, align=WD_PARAGRAPH_ALIGNMENT.CENTER)
    _insert_photos_docx(table.cell(15, 2).merge(table.cell(16, 7)), list(heritage.photos.all()))

    output = io.BytesIO()
    document.save(output)
    file_bytes = output.getvalue()

    safe_name = ''.join(ch if ch.isalnum() or ch in ('-', '_') else '_' for ch in f"{heritage.survey_code}_{heritage.name}")
    filename = f"不可移动文物采集登记表_{safe_name}.docx"
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
    }
    return Response(
        content=file_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )
