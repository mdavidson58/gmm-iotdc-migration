from core.login import gmm_server_login
from core.login import raine_server_login
from core.config import get_config_data as config
from core.constants import GMM_AUTH_TOKEN
from logs import log

logger= log.get_logger("Utilities to get the token details ::")

class Utilities(object):

    def get_gmm_access_token(self):
        token = ''
        if GMM_AUTH_TOKEN:
            token = GMM_AUTH_TOKEN
        else:
            gmm_data = gmm_server_login.login()
            if 200 == gmm_data["status"]:
                token = "{}  {}".format(gmm_data["data"]["token_type"], gmm_data["data"]["access_token"])
            else:
                logger.info(gmm_data["status"])
                logger.error("Error details :: {}".format(gmm_data["error"]))
        return token

    def get_raine_access_token(self):
        token = ''
        raine_data = raine_server_login.login()
        if raine_data is not None:
            if 200 == raine_data["status"]:
                token = "{} {}".format(raine_data["data"]["token_type"], raine_data["data"]["access_token"])
            else:
                logger.info(raine_data["status"])
                logger.error("Error details :: {}".format(raine_data["error"]))
        else:
            logger.error("Raine Server Login Attempt Failed")
        return token


raine_access_token = Utilities().get_raine_access_token()
gmm_access_token= Utilities().get_gmm_access_token()