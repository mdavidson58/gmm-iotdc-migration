from logs import log

from core.config import get_config_data as config

logger = log.get_logger("First Application")
logger.debug("this is a debug message is {}".format(2+3))
logger.info("this is a debug message")
logger.info(config.config)