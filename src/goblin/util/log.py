import logging, os
from logging.handlers import RotatingFileHandler

def setup_logging(level: str = "INFO", path: str = "logs/goblin.log") -> logging.Logger:
    os.makedirs(os.path.dirname(path), exist_ok=True)

    logger = logging.getLogger("goblin")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False  # don't double-log to root

    # Avoid duplicate handlers on re-runs
    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")

        file_h = RotatingFileHandler(path, maxBytes=512_000, backupCount=5)
        file_h.setFormatter(fmt)
        file_h.setLevel(logger.level)
        logger.addHandler(file_h)

        console_h = logging.StreamHandler()
        console_h.setFormatter(fmt)
        console_h.setLevel(logger.level)
        logger.addHandler(console_h)

    return logger