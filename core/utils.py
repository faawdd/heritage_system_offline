from docxtpl import DocxTemplate, InlineImage
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from docx.shared import Mm
from PIL import Image
from urllib.parse import quote
import io
import json
import os
from pathlib import Path

def generate_word_log(record):
    # 1. 加载模板
    template_path = os.path.join(settings.BASE_DIR, 'template.docx')
    doc = DocxTemplate(template_path)
    
    # 2. 准备基础数据上下文
    context = {
        'name': record.site.name,
        'inspector': record.inspector.username if record.inspector else "管理员",
        'time': record.inspect_time.strftime('%Y-%m-%d %H:%M'),
        'status': "正常" if record.is_normal else "异常",
        'details': record.issue_details or "现场无异常情况。",
        'photo': "（未上传照片）" # 默认值
    }

    # 3. 统一的图片处理逻辑（合并之前的两段，只保留这一段）
    if record.photo and os.path.exists(record.photo.path):
        try:
            img = Image.open(record.photo.path)
            width, height = img.size
            
            # 这里设置你想要的尺寸
            if width > height:
                # 横向照片：9厘米宽
                context['photo'] = InlineImage(doc, record.photo.path, width=Mm(130))
            else:
                # 纵向照片：7厘米高
                context['photo'] = InlineImage(doc, record.photo.path, height=Mm(100))
        except Exception as e:
            context['photo'] = f"（图片解析失败: {e}）"

    # 4. 渲染并保存
    doc.render(context)
    
    # 文件名建议加上文物名和 ID，防止覆盖
    file_name = f'巡查日志_{record.site.name}_{record.id}.docx'
    output_path = os.path.join(settings.MEDIA_ROOT, 'logs', file_name)
    
    # 确保文件夹存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    return output_path


def _safe_load_json(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def _normalize_coordinate_item(item, index):
    if not isinstance(item, dict):
        return None

    tower_id = item.get('id') or item.get('tower_no') or item.get('tower') or item.get('杆塔号') or str(index)
    x = item.get('x') or item.get('X') or item.get('coord_x') or item.get('大地2000坐标-X') or ''
    y = item.get('y') or item.get('Y') or item.get('coord_y') or item.get('大地2000坐标-Y') or ''
    lon = item.get('lon') or item.get('longitude') or item.get('经度') or ''
    lat = item.get('lat') or item.get('latitude') or item.get('纬度') or ''

    return {
        'id': str(tower_id),
        'x': str(x),
        'y': str(y),
        'lon': str(lon),
        'lat': str(lat),
    }


def _extract_coordinates(project):
    coordinates_text = getattr(project, 'project_coordinates', '')
    loaded_direct = _safe_load_json(coordinates_text)
    if isinstance(loaded_direct, list):
        direct_normalized = []
        for idx, item in enumerate(loaded_direct, start=1):
            point = _normalize_coordinate_item(item, idx)
            if point:
                direct_normalized.append(point)
        if direct_normalized:
            return direct_normalized

    candidates = []
    for text in [project.remarks, project.ovital_query_record, project.site_survey_record]:
        loaded = _safe_load_json(text)
        if isinstance(loaded, dict):
            for key in ['coordinates', 'coords', 'points', '坐标']:
                if isinstance(loaded.get(key), list):
                    candidates.extend(loaded[key])
        elif isinstance(loaded, list):
            candidates.extend(loaded)

    normalized = []
    for idx, item in enumerate(candidates, start=1):
        point = _normalize_coordinate_item(item, idx)
        if point:
            normalized.append(point)

    if normalized:
        return normalized

    if project.project_lon is not None and project.project_lat is not None:
        return [{
            'id': '1',
            'x': '',
            'y': '',
            'lon': str(project.project_lon),
            'lat': str(project.project_lat),
        }]
    return []


def _extract_attachments(project):
    attachments = []

    for file_field in [
        project.inquiry_letter,
        project.ovital_kml_file,
        project.application_report,
        project.bureau_approval_reply,
        project.project_reply_letter,
        project.file_archive,
    ]:
        if file_field:
            attachments.append(os.path.basename(file_field.name))

    remark_json = _safe_load_json(project.remarks)
    if isinstance(remark_json, dict) and isinstance(remark_json.get('attachments'), list):
        for item in remark_json['attachments']:
            if isinstance(item, dict) and item.get('name'):
                attachments.append(str(item.get('name')))
            elif isinstance(item, str):
                attachments.append(item)

    unique = []
    for name in attachments:
        cleaned = str(name).strip()
        if cleaned and cleaned not in unique:
            unique.append(cleaned)
    return unique


def build_project_doc_context(project):
    sign_dt = project.application_date or project.received_date or timezone.now()
    sign_date = f"{sign_dt.year}年{sign_dt.month}月{sign_dt.day}日"

    year = sign_dt.year
    file_id = project.archive_number or f"鄯文旅字〔{year}〕{project.id}号"
    recipient = '吐鲁番市文物局'
    scale = getattr(project, 'project_scale', '') or ''

    remark_json = _safe_load_json(project.remarks)
    if isinstance(remark_json, dict):
        recipient = remark_json.get('recipient') or recipient
        scale = remark_json.get('scale') or ''

    related_site_text = ''
    if project.related_site:
        related_site_text = f"，涉及文物点：{project.related_site.name}"

    construction_content = getattr(project, 'construction_content', '') or project.survey_conclusion or f"本期拟建项目位于{project.project_unit or '鄯善县境内'}{related_site_text}"
    route_desc = project.ovital_query_record or project.site_survey_record or ''

    coordinates = _extract_coordinates(project)
    attachments = _extract_attachments(project)

    return {
        'file_id': file_id,
        'project_name': project.project_name,
        'recipient': recipient,
        'construction_content': construction_content,
        'route_desc': route_desc,
        'scale': scale,
        'coordinates': coordinates,
        'attachments': attachments,
        'sign_date': sign_date,
    }


def generate_project_docx_response(project, template_path=None):
    if template_path:
        final_template_path = template_path
    else:
        fallback_root = Path(__file__).resolve().parent.parent
        candidate_paths = [
            os.path.join(settings.BASE_DIR, '上行文 {{ file_id }} {{project_name}}.docx'),
            os.path.join(settings.BASE_DIR, 'templates', 'docx', 'project_upward_request_template.docx'),
            os.path.join(settings.BASE_DIR, 'template.docx'),
            str(fallback_root / '上行文 {{ file_id }} {{project_name}}.docx'),
            str(fallback_root / 'templates' / 'docx' / 'project_upward_request_template.docx'),
            str(fallback_root / 'template.docx'),
        ]
        final_template_path = next((path for path in candidate_paths if os.path.exists(path)), None)

    if not final_template_path or not os.path.exists(final_template_path):
        raise FileNotFoundError(f"未找到公文模板文件: {final_template_path}")

    doc = DocxTemplate(final_template_path)
    context = build_project_doc_context(project)
    doc.render(context)

    output = io.BytesIO()
    doc.save(output)
    output.seek(0)

    filename = f"上行文_{project.project_name}_{project.id}.docx"
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
    response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}"
    return response