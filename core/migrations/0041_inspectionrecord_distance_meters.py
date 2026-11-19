from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0040_alter_heritagesite_level_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='inspectionrecord',
            name='distance_meters',
            field=models.FloatField(blank=True, help_text='根据巡查定位与当时文物点坐标计算的近似距离', null=True, verbose_name='距文物点直线距离（米）'),
        ),
    ]
