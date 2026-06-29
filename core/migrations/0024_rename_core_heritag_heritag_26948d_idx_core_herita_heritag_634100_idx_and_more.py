from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_remove_landuseprojectapproval_incoming_doc_num'),
    ]

    # 该迁移原本用于重命名自动索引，但不同Django版本/历史库状态下索引名可能不一致，
    # 会在迁移阶段触发 ValueError（旧索引名不存在）。这里改为幂等 no-op，
    # 保证跨环境部署时 `migrate` 稳定可执行。
    operations = [
        migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop),
    ]
