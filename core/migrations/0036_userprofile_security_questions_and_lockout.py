from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0035_heritagetwolinefile'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='security_questions',
            field=models.JSONField(blank=True, default=list, verbose_name='密码保护问题哈希'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='failed_login_attempts',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='连续登录失败次数'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='login_locked_until',
            field=models.DateTimeField(blank=True, null=True, verbose_name='登录等待截止时间'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='login_locked',
            field=models.BooleanField(default=False, verbose_name='登录已锁定'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='failed_recovery_attempts',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='安全问题失败次数'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='recovery_locked_until',
            field=models.DateTimeField(blank=True, null=True, verbose_name='安全问题验证等待截止时间'),
        ),
    ]