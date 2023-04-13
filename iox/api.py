import logging
import requests
import time
import json
import os
import re
import sys
from datetime import datetime
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from requests.exceptions import HTTPError, RequestException
from utils.encoding_utils import add_auth_header, rainier_login
from utils.form_data_encoder import MultipartEncoder

# from core.utilities import raine_access_token
from logs import log
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

MAX_REQUEST_TIMEOUT = int(os.getenv('MAX_REQUEST_TIMEOUT', 180)) if os.getenv('MAX_REQUEST_TIMEOUT') != '' else 180
MAX_RETRY = int(os.getenv('MAX_RETRY', 1)) if os.getenv('MAX_RETRY') != '' else 1


class TimeoutHTTPAdapter(HTTPAdapter):
    def __init__(self, *args, **kwargs):
        self.timeout = MAX_REQUEST_TIMEOUT
        if "timeout" in kwargs:
            self.timeout = kwargs["timeout"]
            del kwargs["timeout"]
        super().__init__(*args, **kwargs)

    def add_headers(self, request, **kwargs):
        add_auth_header(request, kwargs.get('username'), kwargs.get('password'), kwargs.get('auth_type'))
        pass

    def send(self, request, **kwargs):
        timeout = kwargs.get("timeout")
        self.add_headers(request, username=kwargs.get('username'), password=kwargs.get('password'),
                         auth_type=kwargs.get('auth_type'))
        if timeout is None:
            kwargs["timeout"] = self.timeout
        return super().send(request, **kwargs)


class ApiConnection:
    def __init__(self, address, api_prefix="", username="admin", password="admin", auth_type="Basic", use_https=True,
                 ssl_verify=True, port=443, log_id="", add_headers=add_auth_header, api_key=None):
        self.logger = log.get_logger("ApiConnection.%s" % log_id)
        self.logger.setLevel(logging.DEBUG)

        self.address = address
        self.api_prefix = api_prefix
        self.port = port
        self.username = username
        self.password = password
        self.api_version = "v1"
        self.auth_type = auth_type
        self.api_root = 'appmgr' if auth_type == 'Basic' else 'appmgmt'
        self.use_https = use_https
        self.protocol = "https" if self.use_https else "http"
        self.add_headers = add_headers
        self.x_access_token = None
        self.api_key = api_key
        self.token_expiry_time = None
        self.ssl_verify = ssl_verify

    def do_request(self, url, method, **kwargs):
        try:
            # request_url = "%s://%s:%u/api/%s/%s" % (self.protocol, self.address, self.port, self.api_version, url)
            file_arg_pattern = re.compile(r'files?')
            request_url = "%s:%u%s/api/%s/%s" % (self.address, self.port, self.api_prefix, self.api_version, url) if \
                self.auth_type == 'Basic' else "%s:%u/%s" % (self.address, self.port, url)
            if self.auth_type == 'GMM':
                request_url = "%s/%s" % (self.address, url)
            request_params = kwargs['params'] if 'params' in kwargs else None
            # kwargs['files'] if 'files' in kwargs else None
            request_file = kwargs.get('file', kwargs.get('files'))
            app_file = kwargs['file'] if 'file' in kwargs else None
            multipart_data = None
            response = None

            # if 'x-access-token' not in request_headers:
            #     request_headers['x-access-token'] = access_token
            client = requests.session()
            self.logger.info("Request Url: {}".format(request_url))
            self.x_access_token = self.x_access_token if self.token_expiry_time and self.token_expiry_time > time.time() else None

            self.add_headers(client, self.username, self.password, self.auth_type, self.x_access_token)

            if app_file is not None:
                file = open(app_file, 'rb')
                multipart_data = MultipartEncoder(
                    fields={
                        'file': (app_file, file),
                    }
                )
                client.headers['Content-Type'] = multipart_data.content_type

            if request_file is not None:
                file = open(request_file, 'rb')
                multipart_data = MultipartEncoder(
                    fields={
                        'files': (request_file, file),
                        'filepaths': kwargs['filepaths'] if 'filepaths' in kwargs else None,
                        'newfilenames': kwargs['newfilenames'] if 'newfilenames' in kwargs else None
                    }
                ) if self.auth_type == "Basic" else MultipartEncoder(
                    fields={
                        'file': (request_file, file),
                        'filepath': kwargs.get('filepath'),
                        'newfilename': kwargs.get('newfilename')
                    }
                )
                client.headers['Content-Type'] = multipart_data.content_type

            request_body = None
            if 'data' in kwargs:
                request_body = json.dumps(kwargs['data'])
            now = datetime.now()
            current_time = now.strftime("%H:%M:%S")
            print("Current Time =", current_time)
            self.logger.info("Request Body: {}".format(request_body))

            if 'retries' in kwargs:
                retries = Retry(total=MAX_RETRY, backoff_factor=1, status_forcelist=[429, 401, 500, 502, 503, 504],
                                method_whitelist=["GET", "POST", "PUT"])
                adapter = TimeoutHTTPAdapter(max_retries=retries, username=self.username, password=self.password,
                                             auth_type=self.auth_type)
                client.mount("https://", adapter)
                client.mount("http://", adapter)

            if method == "POST":
                if multipart_data is not None:
                    response = client.post(request_url, params=request_params, data=multipart_data,
                                           verify=self.ssl_verify, timeout=kwargs.get('timeout'))

                else:
                    response = client.post(request_url, params=request_params, json=json.loads(request_body)
                                           if request_body else None, verify=self.ssl_verify,
                                           timeout=kwargs.get('timeout'))

                self.logger.info(response.text)
            elif method == "PUT":
                response = client.put(request_url, params=request_params, json=json.loads(request_body),
                                      verify=self.ssl_verify) if request_body else \
                    client.put(request_url, params=request_params, verify=self.ssl_verify)
                self.logger.info(response.text)
            elif method == "GET":
                response = client.get(request_url, params=request_params, verify=self.ssl_verify)
                self.logger.info(response.text)
            elif method == "DELETE":
                response = client.delete(request_url, params=request_params,json=json.loads(request_body),
                                         verify=self.ssl_verify) if request_body else \
                    client.delete(request_url, params=request_params, verify=self.ssl_verify)
                self.logger.info(response.text)

            return response

        except HTTPError as e:
            self.logger.error(e, exc_info=True)
        except KeyError as e:
            self.logger.error(e, exc_info=True)
        except ConnectionError as e:
            self.logger.error(e, exe_info=True)

    def authenticate(self):
        if self.auth_type == 'Rainier':
            # self.x_access_token = raine_access_token.strip("bearer ")
            self.x_access_token = rainier_login(requests.session(), self.username, self.password,
                                                ssl_verify=self.ssl_verify)
            # Setting expiration after 5 minutes
            self.token_expiry_time = int(time.time()+300)
        elif self.auth_type == 'GMM':
            self.x_access_token = self.api_key
            # Setting expiration after 5 minutes
            self.token_expiry_time = int(time.time()+300)
        else:
            response = self.do_request(f'{self.api_root}/tokenservice', 'POST')
            response_data = response.json()
            self.logger.info(f"Response: {response_data}")
            self.x_access_token = response_data['token'] if response.status_code == 202 else None
            self.token_expiry_time = int(response_data['expiryTime']) if response.status_code == 202 else None
        return self.x_access_token

    def get_default_policy(self, name='FogDirectorDefaultPolicy'):
        self.x_access_token = self.x_access_token if self.token_expiry_time and self.token_expiry_time > time.time() \
            else self.authenticate()
        query_params = {
            'searchByName': name
        }
        response = self.do_request(f'{self.api_root}/policy', 'GET', params=query_params)
        logging.info(response.text)
        return response.json() if response.text != '' else None

    def search_app_details(self, app_name: str):
        self.x_access_token = self.x_access_token if self.token_expiry_time and self.token_expiry_time > time.time() \
            else self.authenticate()
        query_params = {
            'searchByName': app_name
        }
        response = self.do_request(f'{self.api_root}/apps', 'GET', params=query_params)
        logging.info(response.text)
        return response.json() if response.text != '' else None

    def upload_app(self, app_type, app_tar_package):
        self.x_access_token = self.x_access_token if self.token_expiry_time and self.token_expiry_time > time.time() \
            else self.authenticate()
        query_params = {
            'type': app_type if app_type else ''
        }
        response = self.do_request(f'{self.api_root}/apps', 'POST', file=app_tar_package, params=query_params)
        logging.info(response.text)
        if response.status_code != 201:
            raise NameError(f'File upload error occurred for file {app_tar_package}!')
        self.logger.info(f"File: {app_tar_package} Successfully imported")
        return response.json() if response.text != '' else None

    def deploy_app(self, app_id: str, app_version: str, request_payload):
        self.x_access_token = self.x_access_token if self.token_expiry_time and self.token_expiry_time > time.time() \
            else self.authenticate()
        response = self.do_request(f'{self.api_root}/apps/{app_id}/{app_version}/action', 'POST', data=request_payload)
        logging.info(response.text)
        if response.status_code != 200:
            raise Exception(f'Deployment failed for the application with app-id {app_id}')
        self.logger.info(f"Application with app-id {app_id} is deploying...")
        return response.json() if response.text != '' else None

    def undeploy_app(self, app_id: str, app_version: str, request_payload):
        self.x_access_token = self.x_access_token if self.token_expiry_time and self.token_expiry_time > time.time() \
            else self.authenticate()
        response = self.do_request(f'{self.api_root}/apps/{app_id}/{app_version}/action', 'POST', data=request_payload)
        logging.info(response.text)
        if response.status_code != 200:
            raise Exception(f'Uninstallation failed for the application with app-id {app_id}')
        self.logger.info(f"Application with app-id {app_id} is uninstalling...")
        return response.json() if response.text != '' else None

    def upload_app_data(self, device_id, app_id, app_version, file, filepath=None, new_file_name=None):
        self.x_access_token = self.x_access_token if self.token_expiry_time and self.token_expiry_time > time.time() \
            else self.authenticate()
        if self.auth_type == 'Basic':
            response = self.do_request(f'appmgr/devices/{device_id}/apps/{app_id}/{app_version}/appdata', 'POST',
                                       files=file, filepaths=filepath, newfilenames=new_file_name)
        else:
            response = self.do_request(f'{self.api_root}/devices/{device_id}/apps/{app_id}/{app_version}/appdata', 'POST',
                                       file=file, filepath=filepath, newfilename=new_file_name)
        if response.status_code != 200 and response.text != 'File uploaded':
            raise Exception(f'File upload error occurred for file {file}!')
        self.logger.info(f"File: {file} Successfully uploaded")

    def download_app_data(self, device_id, app_id, app_version):
        self.x_access_token = self.x_access_token if self.token_expiry_time and self.token_expiry_time > time.time() \
            else self.authenticate()

        response = self.do_request(f'{self.api_root}/devices/{device_id}/apps/{app_id}/{app_version}/appdata/export',
                                   'GET')
        if response.status_code != 200 and response.text != '':
            raise Exception(f'File down error occurred for app {app_id}!')

        response_data = response.json()
        download_api_url = response_data['_link'].get('href')
        self.logger.info(f"File download url: {download_api_url} Successfully uploaded")
        download_response = self.do_request(f'{download_api_url.replace("/api/v1", "")}', 'GET')
        data = download_response.content
        return data

    def get_app_details_from_device(self, device_id, app_id, app_version):
        self.x_access_token = self.x_access_token if self.token_expiry_time and self.token_expiry_time > time.time() \
            else self.authenticate()
        response = self.do_request(f'{self.api_root}/devices/{device_id}/apps/{app_id}/{app_version}', 'GET')
        if response.status_code != 200:
            raise RequestException(f'No app found with app id {app_id}')
        return response.json() if response.text != '' else None

    def fetch_device_details(self, device_ip, device_name, device_tag, **kwargs):
        self.x_access_token = self.x_access_token if self.token_expiry_time and self.token_expiry_time > time.time() \
            else self.authenticate()
        query_params = {
            'detail': 'app',
            'searchByIp': device_ip if device_ip else '',
            'searchByName': device_name if device_name else '',
            'searchByTags': device_tag if device_tag else '',
            'searchByDeviceDiscoveryStatus': kwargs.get('device_status'),
            'searchByPort': kwargs.get('port'),
            'searchByAnyMatch': kwargs.get('serial_number')
        }
        response = self.do_request(f'{self.api_root}/devices', 'GET', params=query_params)
        return response.json() if response.text != '' else None

    def get_device_detail(self, device_id):
        self.x_access_token = self.x_access_token if self.token_expiry_time and self.token_expiry_time > time.time() \
            else self.authenticate()

        response = self.do_request(f'{self.api_root}/devices/{device_id}', 'GET')
        return response.json() if response.text != '' else None

    def get_unmanaged_apps_on_device(self, device_id, limit=100):
        self.x_access_token = self.x_access_token if self.token_expiry_time and self.token_expiry_time > time.time() \
            else self.authenticate()
        query_params = {
            'limit': limit
        }
        response = self.do_request(f'{self.api_root}/devices/{device_id}/apps', 'GET', params=query_params)
        return response.json() if response.text != '' else None

    def get_job_details(self, job_id: int):
        self.x_access_token = self.x_access_token if self.token_expiry_time and self.token_expiry_time > time.time() \
            else self.authenticate()

        response = self.do_request(f'{self.api_root}/jobs/{job_id}', 'GET')
        logging.info(response.text)
        return response.json() if response.text != '' else None

    # GMM API Calls

    def get_gmm_fog_application(self, org_id: int, limit=100):
        self.x_access_token = self.x_access_token if self.token_expiry_time and self.token_expiry_time > time.time() \
            else self.authenticate()
        query_params = {
            'limit': limit
        }
        response = self.do_request(f'organizations/{org_id}/fog_applications', 'GET',
                                   params=query_params)
        logging.info(response.text)
        return response.json() if response.text != '' else None

    def get_gmm_fog_app_details(self, org_id: int, app_id: int):
        self.x_access_token = self.x_access_token if self.token_expiry_time and self.token_expiry_time > time.time() \
            else self.authenticate()
        response = self.do_request(f'organizations/{org_id}/fog_applications/{app_id}', 'GET')
        logging.info(response.text)
        return response.json() if response.text != '' else None

    def get_gmm_fog_installation(self, app_id: int, limit=100):
        self.x_access_token = self.x_access_token if self.token_expiry_time and self.token_expiry_time > time.time() \
            else self.authenticate()
        query_params = {
            'limit': limit
        }
        response = self.do_request(f'fog_applications/{app_id}/fog_installations', 'GET',
                                   params=query_params)
        logging.info(response.text)
        return response.json() if response.text != '' else None

    def get_gmm_fog_installation_detail(self, installation_id: int):
        self.x_access_token = self.x_access_token if self.token_expiry_time and self.token_expiry_time > time.time() \
            else self.authenticate()
        response = self.do_request(f'fog_installations/{installation_id}', 'GET')
        logging.info(response.text)
        return response.json() if response.text != '' else None

    def get_gmm_templates(self, org_id: int, limit=100):
        self.x_access_token = self.x_access_token if self.token_expiry_time and self.token_expiry_time > time.time() \
            else self.authenticate()
        query_params = {
            'limit': limit
        }
        response = self.do_request(f'organizations/{org_id}/application_templates', 'GET',
                                   params=query_params)
        logging.info(response.text)
        return response.json() if response.text != '' else None

    def get_gmm_template_detail(self, template_id: int):
        self.x_access_token = self.x_access_token if self.token_expiry_time and self.token_expiry_time > time.time() \
            else self.authenticate()
        response = self.do_request(f'application_templates/{template_id}', 'GET')
        logging.info(response.text)
        return response.json() if response.text != '' else None

    def get_gmm_policies(self, org_id: int, limit=100):
        self.x_access_token = self.x_access_token if self.token_expiry_time and self.token_expiry_time > time.time() \
            else self.authenticate()
        query_params = {
            'limit': limit
        }
        response = self.do_request(f'organizations/{org_id}/application_deploy_policies', 'GET',
                                   params=query_params)
        logging.info(response.text)
        return response.json() if response.text != '' else None

    def get_gmm_policy_detail(self, policy_id: int):
        self.x_access_token = self.x_access_token if self.token_expiry_time and self.token_expiry_time > time.time() \
            else self.authenticate()
        response = self.do_request(f'application_deploy_policies/{policy_id}', 'GET')
        logging.info(response.text)
        return response.json() if response.text != '' else None
