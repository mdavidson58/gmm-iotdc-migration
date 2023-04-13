import yaml
import os
from logs import log

logger = log.get_logger("Loading data from  Config.yml :: ")


class Config(object):

    def __init__(self):
        self.config= self.get_config_details()
        self.gmm_server = self.get_gmm_server_data()
        self.raine_server= self.get_raine_server_data()
        self.app_migration_vars = self.get_app_migration_config_data()

    def get_config_details(self):
        try:
            with open(r'config/config.yml') as file:
                config_data = yaml.load(file, Loader=yaml.FullLoader)
                # logger.info("Config data load successfully")
                # Override the values if environment variables passed
                if os.getenv('base_url'):
                    config_data['RAINE_SERVER_URLS']['base_url'] = config_data['RAINE_SERVER_URLS']['base_url'].replace(
                        config_data['APP_MIGRATION_CONFIG_VARS']['base_url'], os.getenv('base_url'))
                    config_data['APP_MIGRATION_CONFIG_VARS']['base_url'] = os.getenv('base_url',
                                                                                     config_data['APP_MIGRATION_CONFIG_VARS'][
                                                                                      'base_url'])

                config_data['APP_MIGRATION_CONFIG_VARS']['api_user'] = os.getenv('api_user',
                                                                                 config_data['APP_MIGRATION_CONFIG_VARS'][
                                                                                  'api_user'])
                config_data['APP_MIGRATION_CONFIG_VARS']['api_password'] = os.getenv('api_password',
                                                                                     config_data['APP_MIGRATION_CONFIG_VARS'][
                                                                                      'api_password'])
                config_data['APP_MIGRATION_CONFIG_VARS']['tenant_id'] = os.getenv('tenant_id',
                                                                                  config_data['APP_MIGRATION_CONFIG_VARS'][
                                                                                   'tenant_id'])
            return config_data
        except Exception  as e:
            logger.info("Failed to load Config data:::")
            logger.error(e)
            return {}

    def get_gmm_server_data(self):
        data = None
        try:
            data = self.config.get("GMM_SERVER_URLS")
        except Exception as e:
            logger.info("Exception occurred to get GMM Server Details")
            logger.error(e)
        return data

    def get_raine_server_data(self):
        data = None
        try:
            data = self.config.get("RAINE_SERVER_URLS")
        except Exception as e:
            logger.info("Exception occurred to get RAINE Server Details")
            logger.error(e)
        return data

    def get_app_migration_config_data(self):
        data = None
        try:
            data = self.config.get("APP_MIGRATION_CONFIG_VARS")
        except Exception as e:
            logger.info("Exception occurred to get app migration config variables")
            logger.error(e)
        return data


# #print(Config().config)
# print(Config().gmm_server)
# print(Config().ranie_server)
get_config_data = Config()
