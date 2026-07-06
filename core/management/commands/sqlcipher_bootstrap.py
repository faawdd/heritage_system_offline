import logging

from django.core.management.base import BaseCommand

from heritage_system.sqlcipher.maintenance import bootstrap_sqlcipher_database


class Command(BaseCommand):
    help = 'Validate, backup, migrate, and initialize the SQLCipher database.'

    def handle(self, *args, **options):
        logger = logging.getLogger('django')
        result = bootstrap_sqlcipher_database(logger=logger)

        self.stdout.write(self.style.SUCCESS(f"SQLCipher database ready: {result['database_path']}"))
        if result.get('backup_path'):
            self.stdout.write(f"Backup created: {result['backup_path']}")
