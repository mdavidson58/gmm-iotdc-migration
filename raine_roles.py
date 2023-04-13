from core.config import get_config_data as config
from logs import log
from core.http_request_handler import serve_get_request
from core.http_request_handler import serve_post_request
from core.constants import *
from core.utilities import raine_access_token
from data_migrations.gmm_users import gmm_users_roles

logger = log.get_logger("Raine roles Details:: ")

class RaineRoleDetails(object):

    def get_raine_roles(self):
        try:
            token = raine_access_token
            if token:
                AUTH_HEADERS["Authorization"] = token
                AUTH_HEADERS['x-access-token'] = token
                base_url = config.raine_server.get('base_url')
                role_url = config.raine_server.get("get_roles")
                url = "{}{}{}".format(base_url, role_url, RAINE_TENANT_ID)
                roles_data = serve_get_request(url, AUTH_HEADERS)
                if 200 == roles_data["status"]:
                    print(roles_data["data"])
                    raine_roles = [role['name'].upper() for role in roles_data["data"]["roles"]]
                    logger.info("Raine Total No of roles: {}".format(roles_data["data"]["count"]))
                    logger.info("Raine roles details:: {}".format(roles_data["data"]["roles"]))
                    return {"status": roles_data["status"], "data": raine_roles}
                else:
                    logger.info("Error occurred to retrieve raine roles")
                    logger.error(roles_data["error"])
                    return {"status": roles_data["status"], "error": roles_data["error"]}
            else:
                logger.info("Error occurred getting raine access_token")
                return {"status": 404, "error": "Error occurred getting raine access_token"}
        except Exception as e:
            logger.error("{}{}".format(e, e.message))

    def create_raine_roles(self):
        try:
            token = raine_access_token
            role_ids = {}
            if token:
                AUTH_HEADERS["Authorization"] = token
                AUTH_HEADERS['x-access-token'] = token
                base_url = config.raine_server.get('base_url')
                role_url = config.raine_server.get("create_roles")
                url = "{}{}".format(base_url, role_url)
                # checking for the permission on this GMM user role which is not present in raine
                new_roles = self.check_user_roles(gmm_users_roles["data"], self.get_raine_roles()["data"])
                if new_roles:
                    for new_role in new_roles:
                        pay_load_role = {
                            "owner_tenant_id": RAINE_TENANT_ID,
                            "service_name": RAINE_SERVICE_NAME,
                            "description": "GMM Admin Created from API",
                            "permission": RAINE_PERMISSIONS[new_role]
                            }
                        raine_role_data = serve_post_request(url, AUTH_HEADERS, pay_load_role)
                        if 200 == raine_role_data["status"]:
                            print(raine_role_data["data"])
                            role_ids[new_role] = raine_role_data['data']
                            logger.info("Raine role Created successfully:: {}".format(raine_role_data["data"]))
                            return {"status": raine_role_data["status"], "data": role_ids}
                        else:
                            logger.info("Error occurred to retrieve raine roles")
                            logger.error(raine_role_data["error"])
                            return {"status": raine_role_data["status"], "error": raine_role_data["error"]}
                else:
                    logger.info("No new role required to add to Raine server")
            else:
                logger.info("Error occurred getting raine access_token")
                return {"status": 404, "error": "Error occurred getting raine access_token"}
        except Exception as e:
            logger.error("{}{}".format(e, e.message))

    def check_user_roles(self,gmm_roles, raine_roles):
        new_roles = [role for role in gmm_roles if role not in raine_roles]
        roles = []
        if new_roles:
            for new_role in new_roles:
                if new_role in RAINE_PERMISSIONS.keys():
                    roles.append(new_role)
            return roles
        else:
            return roles





# print(RaineRoleDetails().get_raine_roles())
# print(RaineRoleDetails().create_raine_roles())

get_raine_roles_data = RaineRoleDetails().get_raine_roles()
create_raine_role = RaineRoleDetails().create_raine_roles()

