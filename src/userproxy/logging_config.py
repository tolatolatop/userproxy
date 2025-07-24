import logging.config
import yaml
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'logger_config.yaml')


def setup_logging():
    with open(CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f)
    logging.config.dictConfig(config)
