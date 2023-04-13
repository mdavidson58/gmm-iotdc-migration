from logs import log
from core.http_request_handler import serve_post_request
from core.constants import AUTH_HEADERS
from core.constants import RAINE_AUTH_PAY_LOAD
from core.constants import GMM_AUTH_PAY_LOAD
from core.config import get_config_data as config

logger = log.get_logger("Login  Details::")

class GMMServerLogin(object):

    def login(self):
        try:
            base_url = config.gmm_server.get('base_url')
            auth_url = config.gmm_server.get('auth_url')
            url = base_url + auth_url
            gmm_response = serve_post_request(url, AUTH_HEADERS, GMM_AUTH_PAY_LOAD)
            if 200 == gmm_response["status"]:
                logger.info("GMM Server login  Success")
                return {"status": gmm_response["status"], "data": gmm_response["data"]}
            else:
                logger.info("GMM Server login  Failed:: ")
                return {"status": gmm_response["status"], "error": gmm_response["error"]}
        except Exception as e:
            logger.error("{}{}".format(e, e.message))


class RaineServerLogin(object):

    def login(self):
        try:
            base_url = config.raine_server.get('base_url')
            auth_url = config.raine_server.get('auth_url')
            url = base_url + auth_url
            raine_response = serve_post_request(url, AUTH_HEADERS, RAINE_AUTH_PAY_LOAD)
            if 200 == raine_response["status"]:
                logger.info("Raine Server login  Success")
                return {"status": raine_response["status"], "data": raine_response["data"]}
            else:
                logger.info("Raine Server login  Failed:: ")
                logger.error(raine_response["data"]["message"])
                return {"status": raine_response["status"], "error": raine_response["error"]}
        except Exception as e:
            logger.error("{}{}".format(e, e.message))


gmm_server_login = GMMServerLogin()
raine_server_login = RaineServerLogin()

# print(gmm_server_login.login())
# print(raine_server_login.login())
