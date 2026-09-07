from django.db import migrations


def backfill_involves_kanerjing(apps, schema_editor):
    """按已核验的涉事文物信息，自动回填历史项目的坎儿井涉及标记。"""
    LandUseProjectApproval = apps.get_model('core', 'LandUseProjectApproval')
    for project in LandUseProjectApproval.objects.filter(is_overlap_artifact=True, involves_kanerjing=False):
        rows = project.overlapped_relics_info if isinstance(project.overlapped_relics_info, list) else []
        if any('坎儿井' in str((row or {}).get('heritage_name') or '') for row in rows):
            project.involves_kanerjing = True
            project.save(update_fields=['involves_kanerjing'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_landuseprojectapproval_workflow_extra_fields'),
    ]

    operations = [
        migrations.RunPython(backfill_involves_kanerjing, noop_reverse),
    ]
