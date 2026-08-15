"""Bounded cleanup of expired database-backed GoreeCloud Manager sessions."""

from __future__ import annotations

from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


DEFAULT_BATCH_SIZE = 100
MAX_BATCH_SIZE = 1000


class Command(BaseCommand):
    help = (
        "Delete expired GoreeCloud Manager database sessions in bounded batches without "
        "printing session identifiers or payloads."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report the number of expired sessions without deleting them.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=f"Expired-session rows to delete per batch (1-{MAX_BATCH_SIZE}).",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]

        if batch_size < 1 or batch_size > MAX_BATCH_SIZE:
            raise CommandError(
                f"--batch-size must be between 1 and {MAX_BATCH_SIZE}."
            )

        cutoff = timezone.now()
        expired = Session.objects.filter(expire_date__lt=cutoff)
        expired_count = expired.count()

        if dry_run:
            self.stdout.write(
                f"expired_sessions={expired_count} deleted_sessions=0 dry_run=true"
            )
            return

        deleted_count = 0
        while True:
            session_keys = list(
                Session.objects.filter(expire_date__lt=cutoff)
                .order_by("expire_date", "session_key")
                .values_list("session_key", flat=True)[:batch_size]
            )
            if not session_keys:
                break

            deleted_in_batch, _ = Session.objects.filter(
                session_key__in=session_keys,
                expire_date__lt=cutoff,
            ).delete()
            deleted_count += deleted_in_batch

        self.stdout.write(
            f"expired_sessions={expired_count} "
            f"deleted_sessions={deleted_count} dry_run=false"
        )
