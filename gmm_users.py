from core.config import get_config_data as config
from core.constants import *
from core.http_request_handler import serve_get_request
from core.utilities import gmm_access_token

from logs import log

logger = log.get_logger("GMM Users data :: ")


class GmmUsers(object):

    def get_gmm_users(self):
        try:
            token = gmm_access_token
            if token:
                AUTH_HEADERS["Authorization"] = token
                base_url = config.gmm_server.get('base_url')
                org_url = config.gmm_server.get("get_organization_members").replace('^', str(GMM_ORGANIZATION_ID))
                url = "{}{}".format(base_url, org_url)
                gmm_members = serve_get_request(url, AUTH_HEADERS)
                if 200 == gmm_members["status"]:
                    members = gmm_members["data"]["memberships"]
                    gmm_users = [{'email': item['user']['email'],
                                  'username': item['user']['name'],
                                  'role': "{}-GMM".format(item['role'].upper()),
                                  'created_at': item['created_at'],
                                  'updated_at': item['updated_at']
                                  } for item in members if item['user']['email'] != 'gwaas-iot@cisco.com']
                    logger.info("Gmm User details:: {}".format(gmm_users))
                    return {"status": gmm_members["status"], "data": gmm_users}
                else:
                    logger.info("Error occurred to retrieve gmm users")
                    logger.error(gmm_members["error"])
                    return {"status": gmm_members["status"], "error": gmm_members["error"]}
            else:
                logger.info("Error occurred getting gmm access_token")
                return {"status": 404, "error": "Error occurred getting gmm access_token"}
        except Exception as e:
            logger.error("{}{}".format(e, e.message))

    def get_gmm_user_listed_roles(self):
        try:
            token = gmm_access_token
            if token:
                AUTH_HEADERS["Authorization"] = token
                base_url = config.gmm_server.get('base_url')
                org_url = config.gmm_server.get("get_organization_members").replace('^', str(GMM_ORGANIZATION_ID))
                url = "{}{}".format(base_url, org_url)
                gmm_members = serve_get_request(url, AUTH_HEADERS)
                if 200 == gmm_members["status"]:
                    gmm_roles = ["{}-GMM".format(item['role'].upper()) for item in gmm_members["data"]["memberships"]]
                    logger.info("Gmm User roles:: {}".format(gmm_roles))
                    return {"status": gmm_members["status"], "data": list(set(gmm_roles))}
                else:
                    logger.info("Error occurred to retrieve gmm users")
                    logger.error(gmm_members["error"])
                    return {"status": gmm_members["status"], "error": gmm_members["error"]}
            else:
                logger.info("Error occurred getting gmm access_token")
                return {"status": 404, "error": "Error occurred getting gmm access_token"}
        except Exception as e:
            logger.error("{}{}".format(e, e.message))


gmm_users_roles = GmmUsers().get_gmm_user_listed_roles()
gmm_users = GmmUsers().get_gmm_users()
