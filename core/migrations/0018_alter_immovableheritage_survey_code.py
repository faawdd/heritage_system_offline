from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_immovableheritage_heritagephoto'),
    ]

    operations = [
        migrations.AlterField(
            model_name='immovableheritage',
            name='survey_code',
            field=models.CharField(
                blank=True,
                default='',
                help_text='系统自动生成，格式：SS-CJ-YYYY-NNNN（如 SS-CJ-2026-0001）',
                max_length=50,
                unique=True,
                verbose_name='采集编号',
            ),
        ),
    ]
