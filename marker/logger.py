import logging
import warnings


def configure_logging():
    # Setup marker logger
    logger = logging.getLogger("marker")

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(logging.DEBUG)

    # Ignore future warnings
    warnings.simplefilter(action="ignore", category=FutureWarning)

    # Set component loglevels
    logging.getLogger("PIL").setLevel(logging.ERROR)
    logging.getLogger("fontTools.subset").setLevel(logging.ERROR)
    logging.getLogger("fontTools.ttLib.ttFont").setLevel(logging.ERROR)
    logging.getLogger("weasyprint").setLevel(logging.CRITICAL)


def get_logger():
    return logging.getLogger("marker")
