from core.config import get_config_data as config
from core.constants import *
from core.http_request_handler import serve_get_request
from core.http_request_handler import serve_post_request
from core.utilities import raine_access_token
from data_migrations.gmm_users import gmm_users_roles
from data_migrations.gmm_users import gmm_users
from data_migrations.raine_roles import get_raine_roles_data
from data_migrations.raine_roles import create_raine_role
from logs import log

logger = log.get_logger("Rainer users data:: ")


class RaineUsers(object):
    def get_raine_users(self):
        try:
            token = raine_access_token
            if token:
                AUTH_HEADERS["Authorization"] = token
                AUTH_HEADERS['x-access-token'] = token
                base_url = config.raine_server.get('base_url')
                org_url = config.raine_server.get("get_users")
                url = "{}{}".format(base_url, org_url)
                print(url)
                raine_data = serve_get_request(url, AUTH_HEADERS)
                if 200 == raine_data["status"]:
                    print(raine_data["data"])
                    raine_users = raine_data["data"]["users"]
                    logger.info("Raine Total No of Users: {}".format(raine_data["data"]["count"]))
                    logger.info("Raine Users details:: {}".format(raine_users))
                    return {"status": raine_data["status"], "data": raine_users}
                else:
                    logger.info("Error occurred to retrieve raine users")
                    logger.error(raine_data["error"])
                    return {"status": raine_data["status"], "error": raine_data["error"]}
            else:
                logger.info("Error occurred getting raine access_token")
                return {"status": 404, "error": "Error occurred getting raine access_token"}
        except Exception as e:
            logger.error("{}{}".format(e, e.message))

    def create_raine_users(self):
        try:
            token = raine_access_token
            new_users,missed_users = [],[]
            if token:
                AUTH_HEADERS["Authorization"] = token
                AUTH_HEADERS['x-access-token'] = token
                base_url = config.raine_server.get('base_url')
                org_url = config.raine_server.get("create_users")
                url = "{}{}".format(base_url, org_url)
                gmm_users_data = gmm_users["data"]
                gmm_roles = gmm_users_roles["data"]
                new_roles_info = create_raine_role
                raine_roles = get_raine_roles_data["data"]
                print(gmm_users_data, gmm_roles, raine_roles)
                print("New roles Information", new_roles_info)
                for gmm_user in gmm_users_data:
                    gmm_role = gmm_user['role']
                    if gmm_role in RAINE_PERMISSIONS.keys() or (new_roles_info is not None and new_roles_info.keys()):
                        user_payload = {
                            "email": gmm_user['email'],
                            "username": gmm_user['email'],
                            "createdAt": gmm_user['created_at'],
                            "updatedAt": gmm_user['updated_at'],
                        }
                        if new_roles_info:
                            if gmm_role in new_roles_info.keys():
                                user_payload["roles"] = [{"tenant_id": RAINE_TENANT_ID,
                                                          "role_id": new_roles_info[gmm_role]}]
                        else:
                            user_payload["roles"] = [{"tenant_id": RAINE_TENANT_ID,
                                                      "role_id": RAINE_USER_CREDENTIALS[gmm_role]}]
                        raine_user_data = serve_post_request(url, AUTH_HEADERS, user_payload)
                        if 200 == raine_user_data["status"]:
                            print("response:::{}".format(raine_user_data))
                            user_id = raine_user_data["data"]["user_uuid"]
                            new_users.append({gmm_user["username"]: user_id})
                            print(new_users)
                            logger.info("Raine Users details:: {}".format(new_users))
                        else:
                            logger.info("Error occurred to retrieve raine users")
                            logger.error(raine_user_data["error"])
                            return {"status": raine_user_data["status"], "error": raine_user_data["error"]}
                    else:
                        logger.info(
                            "Permissions are not exists for {}, \n User not Inserted to raine {}  ".format(gmm_role,
                                                                                                           gmm_user))
                        missed_users.append(gmm_user["username"])
            else:
                logger.info("Error occurred getting raine access_token")
                return {"status": 404, "error": "Error occurred getting raine access_token"}
        except Exception as e:
            logger.error("{}".format(e))
        finally:
            response = {"status": 200, "data": {"new_users": new_users, "skipped_users": missed_users}}
            logger.info("Final data::{}".format(response))
            return response

create_raine_user = RaineUsers().create_raine_users()
print(create_raine_user)
