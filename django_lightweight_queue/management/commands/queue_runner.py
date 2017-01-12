import logging
import daemonize

from django.apps import apps
from django.core.management.base import BaseCommand

from ...utils import get_backend, get_middleware, load_extra_config, configure_logging
from ...runner import runner


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--pidfile', action='store', dest='pidfile', default=None,
            help="Fork and write pidfile to this file.")
        parser.add_argument('--logfile', action='store', dest='logfile', default=None,
            help="Log to the specified file.")
        parser.add_argument('--touchfile', action='store', dest='touchfile', default=None,
            help="touch(1) the specified file after running a job.")
        parser.add_argument('--machine', action='store', dest='machine_number', default='1',
            help="Machine number, for parallelism")
        parser.add_argument('--of', action='store', dest='machine_count', default='1',
            help="Total number of machines running the queues")
        parser.add_argument('--only-queue', action='store', default=None,
            help="Only run the given queue, useful for local debugging")
        parser.add_argument('--config', action='store', default=None,
            help="The path to an additional django-style config file to load")

    def handle(self, **options):
        # Django < 1.8.3 leaves options['verbosity'] as a string so we cast to
        # ensure an int.
        verbosity = int(options['verbosity'])

        level = {
            0: logging.WARNING,
            1: logging.INFO,
            2: logging.DEBUG,
        }[verbosity]

        def log_filename(name):
            try:
                return options['logfile'] % name
            except TypeError:
                return options['logfile']

        def touch_filename(name):
            try:
                return options['touchfile'] % name
            except TypeError:
                return None

        log_fd = configure_logging(
            level=level,
            format='%(asctime)-15s %(process)d %(levelname).1s: %(message)s',
            filename=log_filename('master'),
        )

        log = logging.getLogger()

        # Configuration overrides
        extra_config = options['config']
        if extra_config is not None:
            load_extra_config(extra_config)

        log.info("Starting queue runner")

        # Ensure children will be able to import our backend
        get_backend('dummy')

        get_middleware()
        log.info("Loaded middleware")

        # Ensure children will be able to import most things, but also try and
        # save memory by importing as much as possible before the fork() as it
        # has copy-on-write semantics.
        apps.get_models()
        log.info("Loaded models")

        def run():
            runner(
                log,
                log_filename,
                touch_filename,
                machine_number=int(options['machine_number']),
                machine_count=int(options['machine_count']),
                only_queue=options['only_queue'],
            )

        # fork() only after we have started enough to catch failure, including
        # being able to write to our pidfile.
        if options['pidfile']:
            daemon = daemonize.Daemonize(
                app='queue_runner',
                pid=options['pidfile'],
                action=run,
                keep_fds=[log_fd],
            )
            daemon.start()

        else:
            # No pidfile, don't daemonize, run in foreground
            run()
