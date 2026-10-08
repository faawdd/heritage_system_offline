from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0034_landuseprojectapproval_reuse_preliminary_materials'),
    ]

    operations = [
        migrations.CreateModel(
            name='HeritageTwoLineFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_file', models.FileField(upload_to='heritage/two_line/%Y/%m/', verbose_name='两线源文件')),
                ('original_name', models.CharField(max_length=255, verbose_name='原始文件名')),
                ('uploaded_at', models.DateTimeField(auto_now=True, verbose_name='上传时间')),
                ('site', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='two_line_file', to='core.heritagesite', verbose_name='所属文物点')),
            ],
            options={
                'verbose_name': '文物两线源文件',
                'verbose_name_plural': '文物两线源文件',
            },
        ),
    ]