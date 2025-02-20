import logging
import warnings


def configure_logging():
    logging.basicConfig(level=logging.WARNING)

    logging.getLogger('PIL').setLevel(logging.ERROR)
    warnings.simplefilter(action='ignore', category=FutureWarning)

    logging.getLogger('fontTools.subset').setLevel(logging.ERROR)
    logging.getLogger('fontTools.ttLib.ttFont').setLevel(logging.ERROR)
    logging.getLogger('weasyprint').setLevel(logging.CRITICAL)
