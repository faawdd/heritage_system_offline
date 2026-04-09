from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_alter_inspectionrecord_options_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='KmlUploadRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255, verbose_name='文件标题')),
                ('source_file', models.FileField(upload_to='kml_uploads/%Y/%m/', verbose_name='KML文件')),
                ('threshold_m', models.PositiveIntegerField(default=50, verbose_name='冲突阈值(米)')),
                ('feature_count', models.PositiveIntegerField(default=0, verbose_name='要素数量')),
                ('conflict_count', models.PositiveIntegerField(default=0, verbose_name='冲突数量')),
                ('report_json', models.TextField(blank=True, default='', verbose_name='冲突报告JSON')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('uploaded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='kml_upload_records', to=settings.AUTH_USER_MODEL, verbose_name='上传人')),
            ],
            options={
                'verbose_name': 'KML文件管理',
                'verbose_name_plural': 'KML文件管理',
                'ordering': ['-created_at'],
            },
        ),
    ]
