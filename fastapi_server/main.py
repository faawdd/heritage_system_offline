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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel




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


DB_PATH = Path(settings.DATABASES["default"]["NAME"])
MEDIA_ROOT = Path(settings.MEDIA_ROOT)


app = FastAPI(title="Heritage Patrol FastAPI", version="1.0.0")
security = HTTPBearer(auto_error=False)
User = get_user_model()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    if user.groups.filter(name="文物看护员").exists():
        return "文物看护员"
    return "普通用户"


def serialize_user(user: Any) -> dict:
    groups = list(user.groups.values_list("name", flat=True))
    role = get_user_role(user)
    is_admin = role in {"超级管理员", "管理员"}
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
    if get_user_role(current_user) not in {"超级管理员", "管理员"}:
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
