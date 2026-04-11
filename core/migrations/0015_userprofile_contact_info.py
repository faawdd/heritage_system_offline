from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_kmluploadrecord'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='contact_info',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='联系方式'),
        ),
    ]
