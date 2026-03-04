from docxtpl import DocxTemplate, InlineImage
from django.conf import settings
from docx.shared import Mm 
from PIL import Image
import os

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