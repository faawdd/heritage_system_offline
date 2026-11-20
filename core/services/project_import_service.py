import io
import json
import os
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction

from core.land_project_services import build_project_media_path
from core.models import LandUseProjectApproval, LandUseProjectDocument, LandUseProjectFieldPhoto
from core.services.ai_service import AIConfig, chat_completion, get_ai_config, parse_json_response


MAX_FILE_COUNT = 200
MAX_FILE_SIZE = 30 * 1024 * 1024
MAX_TOTAL_SIZE = 100 * 1024 * 1024
MAX_TEXT_PER_FILE = 2400
MAX_AI_TEXT = 6000
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp'}
VECTOR_EXTENSIONS = {'.kml', '.kmz', '.ovkml', '.ovkmz'}
DOCUMENT_EXTENSIONS = {'.pdf', '.doc', '.docx'}


@dataclass
class ImportFile:
    name: str
    content: bytes
    size: int
    source: str = 'upload'


def _safe_name(name: str) -> str:
    normalized = str(name or '').replace('\\', '/')
    parts = [part for part in normalized.split('/') if part not in {'', '.', '..'}]
    return '/'.join(parts) or '未命名文件'


def _is_ignored_file(name: str) -> bool:
    parts = str(name or '').replace('\\', '/').split('/')
    return any(
        part.startswith('.')
        or part == '__MACOSX'
        or part.lower() == 'thumbs.db'
        for part in parts
    )


def collect_import_files(uploaded_files) -> list[ImportFile]:
    files: list[ImportFile] = []
    total_size = 0
    for upload in uploaded_files:
        upload_name = _safe_name(upload.name)
        if _is_ignored_file(upload_name):
            continue
        upload_size = int(getattr(upload, 'size', 0) or 0)
        if upload_size > MAX_FILE_SIZE:
            raise ValueError(f'文件 {upload_name} 超过单文件 30MB 限制')
        raw = upload.read()
        total_size += len(raw)
        if total_size > MAX_TOTAL_SIZE:
            raise ValueError('项目文件总大小超过 100MB 限制')
        if upload_name.lower().endswith('.zip'):
            files.extend(_unpack_zip(raw, upload_name))
        else:
            files.append(ImportFile(upload_name, raw, len(raw)))
        if len(files) > MAX_FILE_COUNT:
            raise ValueError(f'项目文件数量超过 {MAX_FILE_COUNT} 个限制')
        if sum(item.size for item in files) > MAX_TOTAL_SIZE:
            raise ValueError('项目文件解压后总大小超过 100MB 限制')
    if not files:
        raise ValueError('未找到可导入的项目文件')
    return files


def _unpack_zip(raw: bytes, archive_name: str) -> list[ImportFile]:
    unpacked: list[ImportFile] = []
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            expanded_size = sum(item.file_size for item in archive.infolist() if not item.is_dir())
            if expanded_size > MAX_TOTAL_SIZE:
                raise ValueError('压缩包解压后超过 100MB 限制')
            for item in archive.infolist():
                if item.is_dir() or item.filename.startswith('__MACOSX/'):
                    continue
                name = _safe_name(f'{archive_name.rsplit(".", 1)[0]}/{item.filename}')
                if _is_ignored_file(name):
                    continue
                content = archive.read(item)
                if len(content) > MAX_FILE_SIZE:
                    raise ValueError(f'压缩包成员 {name} 超过单文件 30MB 限制')
                unpacked.append(ImportFile(name, content, len(content), source=archive_name))
    except zipfile.BadZipFile as exc:
        raise ValueError('上传的压缩包不是有效 ZIP 文件') from exc
    return unpacked


def _extract_text(item: ImportFile) -> str:
    ext = os.path.splitext(item.name)[1].lower()
    try:
        if ext in {'.txt', '.csv', '.md', '.json', '.xml', '.kml', '.ovkml'}:
            return item.content.decode('utf-8-sig', errors='ignore')[:MAX_TEXT_PER_FILE]
        if ext == '.docx':
            from docx import Document

            doc = Document(io.BytesIO(item.content))
            return _normalize_extracted_text(
                '\n'.join(p.text for p in doc.paragraphs if p.text.strip())
            )[:MAX_TEXT_PER_FILE]
        if ext == '.pdf':
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(item.content))
            pages = []
            for page in reader.pages[:4]:
                pages.append(page.extract_text() or '')
                if sum(len(value) for value in pages) >= MAX_TEXT_PER_FILE:
                    break
            return _normalize_extracted_text('\n'.join(pages))[:MAX_TEXT_PER_FILE]
    except Exception:
        return ''
    return ''


def _normalize_extracted_text(text: str) -> str:
    normalized = text.replace('\u0000', ' ').replace('\r', '\n')
    normalized = re.sub(r'[ \t\f\v]+', ' ', normalized)
    normalized = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', normalized)
    return normalized.strip()


def _clean_metadata_value(value: str) -> str:
    normalized = re.sub(
        r'[\s、，,；;。:：]+$',
        '',
        str(value or '').strip(),
    )
    normalized = re.sub(r'^(?:现有|原有|为现有|该)', '', normalized).strip()
    return normalized[:120]


def _has_metadata_value(value: Any) -> bool:
    return str(value or '').strip() not in {'', '待补充', '未知', '未识别', 'N/A', 'null', 'None'}


def _clean_company_value(value: str) -> str:
    normalized = _clean_metadata_value(value)
    return re.sub(r'^.*?(?:关于申请核实|关于核实|申请核实)', '', normalized).strip()


def _heuristic_metadata(files: list[ImportFile], texts: dict[str, str]) -> dict[str, Any]:
    combined = '\n'.join(texts.values())
    filenames = '\n'.join(item.name for item in files)
    searchable = f'{combined}\n{filenames}'
    project_name = ''
    company_name = ''
    date_match = re.search(r'(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})', searchable)
    for pattern in (
        r'项目名称\s*[：:]\s*([^\n\r，,。；;]{2,100})',
        r'工程名称\s*[：:]\s*([^\n\r，,。；;]{2,100})',
        r'拟在[^\n。；;]{0,40}?建设\s*([^\n\r，,。；;]{2,100}?建设项目)',
        r'拟建设\s*([^\n\r，,。；;]{2,100}?建设项目)',
        r'关于建设\s*([^\n\r，,。；;]{2,100}?建设项目)',
        r'关于(.{2,100}?(?:项目|工程))(?:建设|选址|规划)?(?:事宜|申请)?的函',
        r'([^/\n\r]{2,100}?(?:项目|工程))(?:[-_（( ]*)?(?:查询函|来函|选址申请|建设申请|请示)',
    ):
        match = re.search(pattern, searchable)
        if match:
            project_name = _clean_metadata_value(match.group(1))
            break
    for pattern in (
        r'(?:建设单位|企业单位|项目单位|来函单位|申报单位)\s*[：:]\s*([^\n\r，,。；;]{2,100})',
        r'([^\n\r/，,。；;]{2,60}(?:集团有限公司|有限责任公司|股份有限公司|有限公司|供电公司|电力公司))',
    ):
        match = re.search(pattern, searchable)
        if match:
            company_name = _clean_company_value(match.group(1))
            break
    if not project_name and files:
        preferred_file = next(
            (
                item for item in files
                if os.path.splitext(item.name)[1].lower() in {'.kml', '.kmz'}
                and re.search(r'建设项目', item.name)
            ),
            files[0],
        )
        first_path = preferred_file.name.split('/')
        candidate = first_path[0] if len(first_path) > 1 else os.path.splitext(first_path[0])[0]
        project_name = re.sub(r'(?i)\.(zip|rar)$', '', _clean_metadata_value(candidate))
        project_name = re.sub(
            r'^.{2,100}?(?=(?:多式联运|光伏|风电|道路|铁路|高速|桥梁|水利|项目))',
            '',
            project_name,
            count=1,
        )
        project_name = re.sub(r'[\s（(]*\(?\d+\)?[\s）)]*$', '', project_name)
    if not company_name:
        company_name = ''
    incoming_doc_date = ''
    if date_match:
        try:
            incoming_doc_date = date(*(int(value) for value in date_match.groups())).isoformat()
        except ValueError:
            pass
    return {
        'project_name': project_name,
        'company_name': company_name,
        'incoming_doc_date': incoming_doc_date,
        'attachments': [_heuristic_attachment(item) for item in files],
    }


def _heuristic_attachment(item: ImportFile) -> dict[str, str]:
    ext = os.path.splitext(item.name)[1].lower()
    lower_name = item.name.lower()
    inferred_type = 'official_doc' if ext in DOCUMENT_EXTENSIONS else 'other'
    category = 'other'
    if ext in VECTOR_EXTENSIONS:
        inferred_type = 'preliminary_kml'
    elif ext in IMAGE_EXTENSIONS:
        inferred_type = 'field_photo'
    elif any(word in lower_name for word in ('查询函', '来函', '申请')):
        category = 'incoming_request'
    elif any(word in lower_name for word in ('现场', '勘查', '照片', '选址')):
        inferred_type = 'field_photo' if ext in IMAGE_EXTENSIONS else inferred_type
    elif any(word in lower_name for word in ('复函', '批复')):
        category = 'city_reply'
    return {'name': item.name, 'file_type': inferred_type, 'category': category, 'reason': '按文件类型和名称识别'}


def analyze_project_files(files: list[ImportFile]) -> dict[str, Any]:
    texts = {item.name: _extract_text(item) for item in files}
    manifest = _heuristic_metadata(files, texts)
    excerpt_parts = []
    remaining = MAX_AI_TEXT
    for name, text in texts.items():
        if not text or remaining <= 0:
            continue
        snippet = text[: min(remaining, MAX_TEXT_PER_FILE)]
        excerpt_parts.append(f'### {name}\n{snippet}')
        remaining -= len(snippet)

    prompt = {
        'manifest': [
            {
                'name': item.name,
                'size': item.size,
                'source': item.source,
                'file_type': next(
                    (attachment['file_type'] for attachment in manifest['attachments'] if attachment['name'] == item.name),
                    'other',
                ),
            }
            for item in files
        ],
        'text_excerpts': '\n\n'.join(excerpt_parts),
    }
    system_prompt = (
        '你是文物保护建设项目归档助手。只依据提供的有限文件摘要识别信息，不推测不存在的数据。'
        '附件类型已由本地规则判断，你只识别项目元数据。必须返回JSON，字段：project_name、company_name、'
        'incoming_doc_date。日期格式为YYYY-MM-DD，无法确定的字段返回空字符串。'
    )
    warning = ''
    try:
        config = get_ai_config()
        import_config = AIConfig(
            provider=config.provider,
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            temperature=0.1,
            system_prompt='',
            timeout=min(config.timeout, 45),
            max_tokens=600,
        )
        result = parse_json_response(
            chat_completion(
                [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': json.dumps(prompt, ensure_ascii=False)},
                ],
                config=import_config,
                temperature=0.1,
                max_tokens=600,
            )
        )
        for key in ('project_name', 'company_name', 'incoming_doc_date'):
            if not _has_metadata_value(result.get(key)):
                result[key] = manifest[key]
        result['project_name'] = _clean_metadata_value(result.get('project_name', ''))
        result['company_name'] = _clean_company_value(result.get('company_name', ''))
        result['attachments'] = manifest['attachments']
    except ValueError as exc:
        result = manifest
        warning = str(exc)

    result['warnings'] = [warning] if warning else []
    result['file_count'] = len(files)
    result['total_size'] = sum(item.size for item in files)
    result['token_strategy'] = f'仅提交文件清单及最多 {MAX_AI_TEXT} 字符摘要，未上传原始二进制文件内容'
    return result


def create_project_from_files(files: list[ImportFile], metadata: dict[str, Any], user) -> LandUseProjectApproval:
    project_name = str(metadata.get('project_name') or '').strip()
    company_name = str(metadata.get('company_name') or '').strip()
    date_text = str(metadata.get('incoming_doc_date') or '').strip()
    if not _has_metadata_value(project_name) or not _has_metadata_value(company_name):
        raise ValueError('请补充项目名称和企业单位')
    try:
        incoming_date = datetime.strptime(date_text, '%Y-%m-%d').date() if date_text else date.today()
    except ValueError as exc:
        raise ValueError('来函日期格式应为 YYYY-MM-DD') from exc

    attachments = metadata.get('attachments') if isinstance(metadata.get('attachments'), list) else []
    attachment_map = {
        str(item.get('name')): item
        for item in attachments
        if isinstance(item, dict) and item.get('name')
    }
    saved_paths: list[str] = []
    try:
        with transaction.atomic():
            project = LandUseProjectApproval.objects.create(
                project_name=project_name,
                preliminary_project_name=project_name,
                company_name=company_name,
                incoming_doc_date=incoming_date,
                receive_date=date.today(),
            )
            for item in files:
                assignment = attachment_map.get(item.name) or _heuristic_attachment(item)
                _archive_file(project, item, assignment, user, saved_paths)
            return project
    except Exception:
        for path in saved_paths:
            if default_storage.exists(path):
                default_storage.delete(path)
        raise


def _archive_file(
    project: LandUseProjectApproval,
    item: ImportFile,
    assignment: dict[str, Any],
    user,
    saved_paths: list[str],
) -> None:
    file_type = str(assignment.get('file_type') or 'other')
    filename = os.path.basename(item.name)
    category = str(assignment.get('category') or 'other')
    extension = os.path.splitext(filename)[1].lower()
    if file_type in {'preliminary_kml', 'kml'}:
        if extension not in VECTOR_EXTENSIONS:
            raise ValueError(f'{filename} 归档为矢量文件时仅支持 KML/KMZ')
        section = 'preliminary_selection' if file_type == 'preliminary_kml' else 'kml'
        path = default_storage.save(
            build_project_media_path(project, section, filename),
            ContentFile(item.content),
        )
        saved_paths.append(path)
        if file_type == 'preliminary_kml':
            project.preliminary_kml_file_path = path
            project.save(update_fields=['preliminary_kml_file_path', 'updated_at'])
        else:
            project.kml_file_path = path
            project.save(update_fields=['kml_file_path', 'updated_at'])
    elif file_type == 'field_photo':
        if extension not in IMAGE_EXTENSIONS:
            raise ValueError(f'{filename} 归档为现场照片时仅支持图片格式')
        path = default_storage.save(
            build_project_media_path(project, 'field_checks', filename),
            ContentFile(item.content),
        )
        saved_paths.append(path)
        LandUseProjectFieldPhoto.objects.create(project=project, photo_path=path, note='智能导入')
    elif file_type == 'official_doc':
        if extension not in DOCUMENT_EXTENSIONS:
            raise ValueError(f'{filename} 归档为公文时仅支持 PDF/DOC/DOCX')
        valid_categories = {code for code, _label in LandUseProjectDocument.CATEGORY_CHOICES}
        if category not in valid_categories:
            category = LandUseProjectDocument.CATEGORY_OTHER
        path = default_storage.save(
            build_project_media_path(project, os.path.join('documents', category), filename),
            ContentFile(item.content),
        )
        saved_paths.append(path)
        LandUseProjectDocument.objects.create(
            project=project,
            category=category,
            title=filename.rsplit('.', 1)[0],
            file_path=path,
            file_name=filename,
            file_size=item.size,
            note='智能导入',
            uploaded_by=user,
        )
    elif file_type in {'archaeology_report', 'kanerjing_plan'}:
        if extension != '.pdf':
            raise ValueError(f'{filename} 归档为报告或保护方案时仅支持 PDF')
        section = 'archaeology' if file_type == 'archaeology_report' else 'kanerjing'
        path = default_storage.save(
            build_project_media_path(project, section, filename),
            ContentFile(item.content),
        )
        saved_paths.append(path)
        field = 'archaeology_report_path' if file_type == 'archaeology_report' else 'kanerjing_protection_plan_path'
        setattr(project, field, path)
        project.save(update_fields=[field, 'updated_at'])
    else:
        path = default_storage.save(
            build_project_media_path(project, 'other', filename),
            ContentFile(item.content),
        )
        saved_paths.append(path)
        LandUseProjectDocument.objects.create(
            project=project,
            category=LandUseProjectDocument.CATEGORY_OTHER,
            title=filename.rsplit('.', 1)[0],
            file_path=path,
            file_name=filename,
            file_size=item.size,
            note='智能导入：未分类附件',
            uploaded_by=user,
        )
