"""
Django management command to run the Event Subscriber.

Usage:
    python manage.py run_event_subscriber

This command starts the Event Subscriber that listens to Redis Streams
from Go services (batch-service, cluster-service) and processes events.
"""

from django.core.management.base import BaseCommand
from apps.operations.event_subscriber import EventSubscriber


class Command(BaseCommand):
    help = 'Run event subscriber for Redis Streams from Go services'

    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose logging',
        )

    def handle(self, *args, **options):
        """Execute the command."""
        verbose = options.get('verbose', False)

        if verbose:
            self.stdout.write(
                self.style.SUCCESS('Starting Event Subscriber in verbose mode...')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('Starting Event Subscriber...')
            )

        # Create and run subscriber
        subscriber = EventSubscriber()

        try:
            # This blocks indefinitely until interrupted
            subscriber.run_forever()

        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING('\nInterrupted by user (Ctrl+C)')
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {e}')
            )
            raise
