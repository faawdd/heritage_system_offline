from django.db import migrations


def add_missing_file_name_column(apps, schema_editor):
    model = apps.get_model('core', 'LandUseProjectDocument')
    table = model._meta.db_table
    field = model._meta.get_field('file_name')
    with schema_editor.connection.cursor() as cursor:
        columns = {
            description.name
            for description in schema_editor.connection.introspection.get_table_description(
                cursor,
                table,
            )
        }
    if field.column not in columns:
        schema_editor.add_field(model, field)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0041_inspectionrecord_distance_meters'),
    ]

    operations = [
        migrations.RunPython(add_missing_file_name_column, migrations.RunPython.noop),
    ]
