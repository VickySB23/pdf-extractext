import logging
import sys

def setup_logger():
    logger = logging.getLogger("pdf_extractor")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(handler)
        
    return logger
logger = setup_logger()