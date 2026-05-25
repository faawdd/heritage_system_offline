from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0018_alter_immovableheritage_survey_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="immovableheritage",
            name="coord_list",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="区块2采集的多点坐标信息，含类型、经纬高、说明与备注",
                verbose_name="区块2坐标点列表",
            ),
        ),
    ]
