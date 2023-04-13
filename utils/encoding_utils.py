import base64
from logs import log
from core.config import get_config_data as config


logger = log.get_logger("Login  Details Test::")


def base64_encode(s):
    return base64.b64encode(s.encode('ascii'))


def rainier_login(req, username, password, grant_type='password', ssl_verify=True, client_secret=None, client_id=None):
    base_url = config.raine_server.get('base_url')
    auth_url = config.raine_server.get('auth_url')
    url = base_url + auth_url
    auth_header = {
        'Content-type':  'application/json',
        'Accept': 'application/json',
    }
    login_req_body = {
        "username": username,
        "password": password,
        "grant_type": grant_type
    }
    req.headers = auth_header
    rainier_response = req.post(url, json=login_req_body, verify=ssl_verify)
    if rainier_response.status_code == 200:
        response_data = rainier_response.json()
        # logger.info("Raine Server login  Success")
        return response_data['access_token']
    else:
        logger.info("Raine Server login  Failed:: ")
        logger.error(rainier_response.text)
        raise Exception("Rainier Login Failed!")


def add_auth_header(req, username, password, type_auth='Basic', x_access_token=None):
    """
    Add encoded authentication header to http request
    :param req: http request
    :param username: username
    :param password: password
    :param type_auth: type of authentication by default Basic
    :param x_access_token: x access token for any authenticated request
    :return: None
    """
    credentials = '%s:%s' % (username, password)
    base64_credentials = base64_encode(credentials)  # [:-1]
    auth = "{} {}".format(type_auth, base64_credentials.decode('ascii'))
    # req.add_header("Authorization", auth) if not x_access_token else req.add_header("x-token-id", x_access_token)
    if type_auth == 'Basic' and not x_access_token:
        req.headers["Authorization"] = auth
    elif type_auth == 'Rainier':
        req.headers['Authorization'] = "Bearer " + x_access_token if x_access_token \
            else "Bearer " + rainier_login(req, username, password)
        req.headers["X-Tenant-Id"] = config.app_migration_vars.get("tenant_id")
    elif type_auth == 'GMM':
        req.headers['Authorization'] = "Bearer " + x_access_token
    else:
        req.headers["x-token-id"] = x_access_token
