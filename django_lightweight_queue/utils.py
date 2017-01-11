import logging
import importlib
import imp
import warnings

from django.apps import apps
from django.core.exceptions import MiddlewareNotUsed
from django.utils.lru_cache import lru_cache
from django.utils.module_loading import module_has_submodule

from . import app_settings

def load_extra_config(file_path):
    extra_settings = imp.load_source('extra_settings', file_path)

    def get_setting_names(module):
        return set(name for name in dir(module) if name.isupper())

    setting_names = get_setting_names(app_settings)
    extra_names = get_setting_names(extra_settings)

    unexpected_names = extra_names - setting_names
    if unexpected_names:
        unexpected_str = "' ,'".join(unexpected_names)
        warnings.warn("Ignoring unexpected setting(s) '%s'." % (unexpected_str,))

    override_names = setting_names & extra_names
    for name in override_names:
        setattr(app_settings, name, getattr(extra_settings, name))

def configure_logging(level, format, filename):
    """
    Like ``logging.basicConfig`` but we use WatchedFileHandler so that we play
    nicely with logrotate and similar tools.

    We also unconditionally remove all existing handlers.

    Returns the file handle of the log file so that we can pass this on to a
    daemon process.
    """

    logging.root.handlers = []

    handler = logging.StreamHandler()
    if filename:
        handler = logging.handlers.WatchedFileHandler(filename)

    handler.setFormatter(logging.Formatter(format))

    logging.root.addHandler(handler)

    if level is not None:
        logging.root.setLevel(level)

    return handler.stream.fileno()

@lru_cache()
def get_path(path):
    module_name, attr = path.rsplit('.', 1)

    module = importlib.import_module(module_name)

    return getattr(module, attr)

@lru_cache()
def get_backend(queue):
    return get_path(app_settings.BACKEND_OVERRIDES.get(
        queue,
        app_settings.BACKEND,
    ))()

@lru_cache()
def get_middleware():
    middleware = []

    for path in app_settings.MIDDLEWARE:
        try:
            middleware.append(get_path(path)())
        except MiddlewareNotUsed:
            pass

    return middleware

def import_all_submodules(name):
    for app_config in apps.get_app_configs():
        app_module = app_config.module

        try:
            importlib.import_module('%s.%s' % (app_module.__name__, name))
        except ImportError:
            if module_has_submodule(app_module, name):
                raise

try:
    import setproctitle

    original_title = setproctitle.getproctitle()

    def set_process_title(*titles):
        setproctitle.setproctitle("%s %s" % (
            original_title,
            ' '.join('[%s]' % x for x in titles),
        ))
except ImportError:
    def set_process_title(*titles):
        pass
