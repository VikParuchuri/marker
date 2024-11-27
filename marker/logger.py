import logging
import warnings


def configure_logging():
    logging.basicConfig(level=logging.WARNING)

    logging.getLogger('PIL').setLevel(logging.ERROR)
    warnings.simplefilter(action='ignore', category=FutureWarning)
