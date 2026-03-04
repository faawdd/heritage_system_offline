import os
import django
import pandas as pd

# 1. 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'heritage_system.settings')
django.setup()

from core.models import HeritageSite

# 定义中文表头与数据库字段的对应关系
COLUMN_MAPPING = {
    '文物名称': 'name',
    '四普编号': 'sip_code',
    '文物类别': 'category',
    '保护级别': 'level',
    '详细地址': 'address',
    '经度': 'longitude',
    '纬度': 'latitude',
    '管理单位': 'manager',
    '现状描述': 'description'
}

# 类别映射（如果你的 models.py 使用了代码缩写，这里需要转换）
# 如果 models 里直接存中文，则不需要这个转换
CATEGORY_MAP = {
    '古建筑': 'GJZ',
    '古遗址': 'GYZ',
    '古墓葬': 'GMZ',
    '石窟寺及石刻': 'SKT',
    '近现代重要史迹及代表性建筑': 'JDJW'
}

def import_excel(file_path):
    if not os.path.exists(file_path):
        print(f"错误：找不到文件 {file_path}")
        return

    # 读取 Excel
    df = pd.read_excel(file_path)
    
    # 将中文列名替换为英文变量名
    df = df.rename(columns=COLUMN_MAPPING)

    success_count = 0
    for index, row in df.iterrows():
        try:
            # 处理类别转换（可选）
            cat_value = row.get('category')
            final_category = CATEGORY_MAP.get(cat_value, 'QT') # 找不到就归类为其他

            # 写入数据库
            site, created = HeritageSite.objects.update_or_create(
                sip_code=row['sip_code'],
                defaults={
                    'name': row['name'],
                    'category': final_category,
                    'level': row.get('level', 'DS'),
                    'address': row.get('address', ''),
                    'longitude': float(row['longitude']),
                    'latitude': float(row['latitude']),
                    'manager': row.get('manager', '本级文物部门'),
                }
            )
            print(f"{'新增' if created else '更新'}: {site.name}")
            success_count += 1
        except Exception as e:
            print(f"第 {index+2} 行出错: {e}")

    print(f"\n全部完成！共导入/更新 {success_count} 条数据。")

if __name__ == "__main__":
    import_excel('sip_data.xlsx')