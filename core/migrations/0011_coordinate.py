from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_projectaudit_construction_content_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Coordinate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tower_no', models.CharField(max_length=50, verbose_name='杆塔号')),
                ('cgcs2000_x', models.DecimalField(blank=True, decimal_places=3, max_digits=16, null=True, verbose_name='CGCS2000 X')),
                ('cgcs2000_y', models.DecimalField(blank=True, decimal_places=3, max_digits=16, null=True, verbose_name='CGCS2000 Y')),
                ('longitude', models.FloatField(blank=True, null=True, verbose_name='经度')),
                ('latitude', models.FloatField(blank=True, null=True, verbose_name='纬度')),
                ('is_on_boundary', models.BooleanField(default=False, verbose_name='是否位于保护区边界')),
                ('check_status', models.CharField(choices=[('pending', '待核查'), ('checked', '已核查')], default='pending', max_length=20, verbose_name='核查状态')),
                ('remark', models.CharField(blank=True, default='', max_length=255, verbose_name='位置说明')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='coordinates', to='core.projectaudit', verbose_name='所属工程项目')),
            ],
            options={
                'verbose_name': '杆塔坐标',
                'verbose_name_plural': '杆塔坐标',
                'ordering': ['project_id', 'tower_no'],
            },
        ),
    ]
