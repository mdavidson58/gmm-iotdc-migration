import csv
import re
import os
import traceback
import subprocess
import json
import tarfile
from datetime import datetime
from collections import defaultdict
from requests.exceptions import RequestException
import concurrent.futures
from time import time, sleep
from configparser import ConfigParser

from iox import api, ioxclient
from logs import log

logger = log.get_logger("App Migration:: ")


class Application:
    def __init__(self, app_id: str, gmm_formatted_app_name: str, app_name: str, app_type: str, app_version: str,
                 status: str):
        self.app_id = app_id
        self.imported_app_id = app_id
        self.app_name = app_name
        self.gmm_formatted_app_name = gmm_formatted_app_name
        self.app_type = app_type
        self.app_version = app_version
        self.exported_package_name = None
        self.import_package_name = app_name + '_V' + app_version.replace('.', '_') + '.tar.gz'
        self.app_data_file_name = app_name + '-datamount.tar.gz'
        self.app_config_file_name = 'package_config.ini'
        self.image_url = None
        self.image_tag = app_version
        self.status = status
        self.app_config = None
        self.resource_config = None
        self.need_uninstall = False
        self.deploy_status = None
        self.deploy_error = ""
        self.operational_status = None
        self.deploy_status_msg = ""


class Device:
    def __init__(self, device_id: str, device_ip: str, port: int, serial_number: str, device_name: str,
                 device_status: str, profile_name: str):
        self.device_id = device_id
        self.device_ip = device_ip
        self.device_name = device_name
        self.device_status = device_status
        self.port = port
        self.serial_number = serial_number
        self.profile_name = profile_name
        self.applications = []


class AppMigration:
    """AppMigration class contains all necessary methods and attributes for the application migration
    from GMM to IOT-OD.

    Parameters
    ----------
    api_server : `str`
       The api server where application will be migrated.
    api_user : `str`
       The api user for IOX proxy or FD API.
    api_prefix : `str`
       This an optional parameter and defaulted to empty string if using IOX proxy then may need to be passed.

    """
    MAX_TIMEOUT = 1800

    def __init__(self, iox_client_host: str, iox_user: str, iox_password: str, ssh_key_path: str,
                 api_server: str, api_user: str, api_password: str, network_ip: str = None, network_grp: str = None,
                 vpn_user: str = None, vpn_pwd: str = None, skip_vpn_trust: str = 'n', platform: str = 'linux',
                 port=443, api_prefix="", auth_type="Basic", use_https=True, ssl_verify=True,
                 continue_on_error=False, skip_data_migration=True, skip_starting_app=False, skip_managed_apps=True,
                 gmm_api_server=None, gmm_api_key=None, gmm_org_id=None):
        self.device = None
        self.devices = []
        self.iox_client_host = iox_client_host
        self.iox_user = iox_user
        self.iox_password = iox_password
        self.ssh_key_path = ssh_key_path
        self.network_ip = network_ip
        self.network_grp = network_grp
        self.vpn_user = vpn_user
        self.vpn_pwd = vpn_pwd
        self.skip_vpn_trust = skip_vpn_trust
        # app_package_source can be ova or tar based on app type
        # self.app_package_source = 'ova' if app_type == 'vm' else 'tar'
        self.iot_od_cluster = None
        self.api_server = api_server
        self.gmm_api_server = gmm_api_server
        self.port = port
        self.api_prefix = api_prefix
        self.api_user = api_user
        self.api_password = api_password
        self.auth_type = auth_type
        self.use_https = use_https
        self.ssl_verify = ssl_verify
        self.platform = platform
        self.continue_on_error = continue_on_error
        self.skip_data_migration = skip_data_migration
        self.skip_starting_app = skip_starting_app
        self.skip_managed_apps = skip_managed_apps
        self.gmm_api_key = gmm_api_key
        self.gmm_org_id = gmm_org_id
        self.migration_report_data = []
        self.api = api.ApiConnection(self.api_server, self.api_prefix, self.api_user, self.api_password, self.auth_type,
                                     self.use_https, self.ssl_verify, self.port, log_id='AppMigration')

        self.gmm_api = api.ApiConnection(self.gmm_api_server, '', None, None, 'GMM', self.use_https, True, 443,
                                         log_id='GMMApiConnection', api_key=gmm_api_key)
        self.any_connect = False
        self._create_vpn_input_file()
        self.ioxclient = ioxclient.IOXClient(self.iox_client_host, self.any_connect, self.iox_user, self.iox_password,
                                             self.ssh_key_path, platform=self.platform)

    def read_device_csv(self, device_file, **kwargs):
        with open(device_file) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            line_count = 0
            for row in csv_reader:
                if line_count == 0:
                    logger.info(f'Column names are {", ".join(row)}')
                    line_count += 1
                else:
                    logger.info(f'\tFound device IP{row[0]} with device name {row[1]}')
                    device_ip = row[0] if row[0] != "" else None
                    device_name = row[1] if row[1] != "" else None
                    device_details = self.api.fetch_device_details(device_ip=device_ip, device_name=device_name,
                                                                   device_tag=None)
                    self.parse_device_details(device_details)
                    line_count += 1
                    print(f'Processed {line_count} lines.')

    def _create_vpn_input_file(self):
        """ Create a file that will contain all the details for connecting to a vpn network """
        try:
            app_data_dir = os.path.join(os.environ['APP_MIGRATION_DATA_DIR'])
        except KeyError as e:
            # logger.log(str(e) + " is non-existent")
            app_data_dir = os.path.abspath(os.path.join('./archive'))
        try:
            with open(os.path.join(app_data_dir, 'anyconnect.txt'), mode='w') as file_handle:
                file_buffer = []
                if self.network_ip:
                    file_buffer.append(f'connect {self.network_ip}')
                    if self.skip_vpn_trust.lower() == 'y':
                        file_buffer.append('y')
                    if self.network_grp:
                        file_buffer.append(self.network_grp)
                    file_buffer.append(self.vpn_user)
                    file_buffer.append(self.vpn_pwd)
                    file_handle.writelines("%s\n" % line for line in file_buffer)
                    self.any_connect = True
        except IOError as e:
            logger.error(f"Not able to create any-connect vpn input file!\n {e}")
            self.any_connect = False

    def parse_device_details(self, device_details):
        if device_details:
            for device_dtl in device_details.get('data'):
                device = Device(device_dtl['deviceId'], device_dtl['ipAddress'], device_dtl['port'],
                                device_dtl['serialNumber'], device_dtl['hostname'], device_dtl['status'],
                                profile_name=self.device.profile_name)
                if not self.skip_managed_apps:
                    for app in device_dtl['apps']:
                        application = Application(app['appId'], app['name'], self.format_app_name(app['name']), 'DOCKER',
                                                  app['version'], app['status'])
                        safe_makedirs(os.path.join('archive/apps', application.app_name))
                        device.applications.append(application)
                else:
                    response = self.api.get_unmanaged_apps_on_device(device.device_id)
                    for app in response['data']:
                        if app.get("appType") == "UNMANAGED":
                            application = Application(app['appId'], app['name'], self.format_app_name(app['name']),
                                                      'UNMANAGED', app['version'], app['status'])
                            safe_makedirs(os.path.join('archive/apps', application.app_name))
                            device.applications.append(application)

                self.devices.append(device)

    def get_app_present_in_device(self, gmm_app):
        for app in self.device.applications:
            if app.app_name == gmm_app['name'] and app.app_version == gmm_app['version']:
                return app
        return None

    def parse_gmm_device_info(self, gmm_device_info):
        logger.info(f"Parsing GMM device json file {self.device.serial_number}.json...")
        # Get the gmm-data tar package
        try:
            gmm_data_dir = os.path.join(os.environ['APP_MIGRATION_DATA_DIR'])
        except KeyError as e:
            # logger.log(str(e) + " is non-existent")
            gmm_data_dir = os.path.abspath('./archive')

        gmm_data_file_dir = os.path.join(gmm_data_dir, 'gmm_app_details')
        logger.info(f"Gmm Data Files Directory: {os.path.join(gmm_data_dir, 'gmm_app_details')}")
        gmm_apps_dir = os.path.join(gmm_data_file_dir, 'apps')

        for data in gmm_device_info:
            app = data.get('fog_application')
            if app:
                app_obj = self.get_app_present_in_device(app)
                gmm_app_detail_file = app['name'] + '_V' + app['version'].replace('.', '_')
                gmm_app_name = str(app['organization_id']) + '.' + app['name'] + '.' + str(app['id'])

                if not self.is_gmm_data_present(gmm_app_detail_file, dir_name='apps'):
                    raise Exception("Gmm data file not found exception")

                logger.info("Reading the GMM app details json file for getting app interface details...")
                with open(os.path.join(gmm_apps_dir, gmm_app_detail_file + '.json'), 'r') as data_file:
                    app_details = json.load(data_file)
                    app_interfaces = app_details['resources'].get('app_interfaces')
                    data['resources']['app_interfaces'] = app_interfaces

                if app_obj:
                    app_obj.need_uninstall = True
                    app_obj.app_config, app_obj.resource_config = self.get_and_format_gmm_config(data, app_obj)
                else:
                    application = Application(app['id'], gmm_app_name, app['name'], 'docker', app['version'],
                                              data['fog_director_state'])
                    try:
                        # Check the managed app is already present or not
                        if not self.is_managed_app_exists(application.app_name):
                            logger.warning(f"No managed app found for the "
                                           f"application {application.gmm_formatted_app_name}")
                            raise NameError(f"Application with name {application.app_name} is not present in IOT-OD! "
                                            f"so make sure you have already imported the app in IOT-OD!")
                        application.app_config, application.resource_config = self.get_and_format_gmm_config(data,
                                                                                                             application)
                        self.device.applications.append(application)
                    except NameError as err:
                        logger.error(f"Managed application not found for the app {application.gmm_formatted_app_name}!")
                        if not self.continue_on_error:
                            raise NameError(f"Application with name {application.app_name} is not present in IOT-OD! "
                                            f"so make sure you have already imported the app in IOT-OD!")

    def parse_device_info(self, device_info, profile_name):
        if device_info:
            self.device = Device(device_info['deviceId'], device_info['ipAddress'], device_info['port'],
                                 device_info['serialNumber'], device_info['hostname'], device_info['status'],
                                 profile_name=profile_name)
            for app in device_info['apps']:
                application = Application(app['appId'], app['name'], self.format_app_name(app['name']), 'docker',
                                          app['version'], app['status'])
                is_unmanaged = self.is_unmanaged_app(application.gmm_formatted_app_name)
                try:
                    app_data_dir = os.path.join(os.environ['APP_MIGRATION_DATA_DIR'], application.app_name)
                except KeyError as e:
                    # logger.log(str(e) + " is non-existent")
                    app_data_dir = os.path.abspath(os.path.join('./archive/apps', application.app_name))
                if is_unmanaged or not self.skip_managed_apps:
                    try:
                        # Check the managed app is already present or not
                        if not self.is_managed_app_exists(application.app_name):
                            logger.warning(f"No managed app found for the "
                                           f"application {application.gmm_formatted_app_name}")
                            raise NameError(f"Application with name {application.app_name} is not present! so make sure "
                                            f"you have already imported the app for all unmanaged app!")
                        safe_makedirs(app_data_dir)
                        self.device.applications.append(application)
                    except NameError as err:
                        logger.error(f"Managed application not found for the app {application.gmm_formatted_app_name}!")
                        if not self.continue_on_error:
                            raise NameError(f"Application with name {application.app_name} is not present! so make sure "
                                            f"you have already imported the app for all unmanaged app!")
        else:
            # Reset the current migration device record
            self.device = None

    def is_managed_app_exists(self, app_name):
        """ Look for managed app with respect to an unmanaged app in IOT-OD if not present then return False"""
        app_details = self.api.search_app_details(app_name)
        if len(app_details['data']):
            for app in app_details['data']:
                if app['name'] == app_name and app['appType'] != 'UNMANAGED':
                    return True
        return False

    def is_unmanaged_app(self, app_name):
        """ Check that an app is unmanaged in the device or not """
        app_details = self.api.search_app_details(app_name)
        if len(app_details['data']):
            for app in app_details['data']:
                if app['name'] == app_name and app['appType'] == 'UNMANAGED':
                    return True
        return False

    @staticmethod
    def format_app_name(original_app_name):
        """Returns application name after trimming the organization id.

        :param original_app_name: This is the GMM formatted app name

        :return:
        device_app_name : `str`
            application name that the customer wants to have for the installed application
        """
        # trim starting org id
        device_app_name = re.sub(r"^([1-9]+\.)", "", original_app_name)

        # trim the end unique id
        device_app_name = re.sub(r"(\.[1-9]+)$", "", device_app_name)
        # device_app_name = re.sub(r"\.?\d+\.?", "", original_app_name)
        return device_app_name

    def get_all_devices(self, device_status='DISCOVERED'):
        """Returns all devices those were imported into iot-od.

        Calls the IOX proxy api to get all imported devices and return that as a list.

        :return:
        devices : `list`
            a `list` of devices those were imported in the rainier iot-od
        """
        devices = self.api.fetch_device_details(device_ip=None, device_name=None, device_tag=None,
                                                device_status=device_status)
        return devices

    def get_migrated_gmm_devices(self):
        """Returns only the migrated devices those were imported into iot-od with some applications running.

        Read the device json file and find the device details and return that as a list.

        :return:
        devices : `list`
            a `list` of devices those were imported in the rainier iot-od
        """
        try:
            gmm_data_dir = os.path.join(os.environ['APP_MIGRATION_DATA_DIR'])
        except KeyError as e:
            # logger.log(str(e) + " is non-existent")
            gmm_data_dir = os.path.abspath('./archive')

        gmm_app_details_dir = os.path.join(gmm_data_dir, 'gmm_app_details')
        logger.info(f"GMM export details data directory: {gmm_app_details_dir}")
        gmm_devices = []
        for file_name in os.listdir(os.path.join(gmm_app_details_dir, 'devices')):
            serial_no = file_name.strip('.json')
            devices = self.api.fetch_device_details(device_ip=None, device_name=None, device_tag=None,
                                                    serial_number=serial_no)
            for device in devices.get('data', []):
                if device['serialNumber'] == serial_no:
                    gmm_devices.append(device)
                    break
        return gmm_devices

    def get_target_devices(self, device_ip=None, device_name=None, device_tag=None, device_csv=None):
        """Returns all the devices where application should be installed.

        Calls the IOX proxy api to get all filtered devices and return that as a list. Also it will
        instantiate devices so that later we can get the details of the applications from the
        devices list.

        :return:
        devices : `list`
            a `list` of all devices where application need to installed
        """
        device_details = None
        if device_ip or device_name or device_tag:
            device_details = self.api.fetch_device_details(device_ip=device_ip, device_name=device_name,
                                                           device_tag=device_tag)
            self.parse_device_details(device_details)
        elif device_csv:
            self.read_device_csv(device_csv)
        else:
            device_details = self.get_all_devices()
            self.parse_device_details(device_details)
        return device_details

    def get_target_device_details(self, device_ip: str, profile_name: str, port=None, serial_number=None):
        """Returns all the devices where application should be installed.

        Calls the IOX proxy api to get all filtered devices and return that as a list. Also it will
        instantiate devices so that later we can get the details of the applications from the
        devices list.

        :return:
        devices : `list`
            a `list` of all devices where application need to installed
        """
        if device_ip or serial_number:
            device_details = self.api.fetch_device_details(device_ip=device_ip, device_name=None,
                                                           device_tag=None, port=port, serial_number=serial_number)
            device = device_details.get('data')[0] if len(device_details.get('data')) else None
            if device is None:
                logger.info(f"No device found with ip {device_ip} or serial number {serial_number}!")
            self.parse_device_info(device, profile_name)
            return device

    def extract_app_package(self):
        """ Extract out all the files from the exported application tar """
        for device in self.devices:
            for app in device.applications:
                file_name = os.path.join('archive/apps', app.app_name, app.exported_package_name)
                output_path = os.path.join('archive/apps', app.app_name)
                exit_code = os.system('tar -xzvf {0} -C {1}'.format(file_name, output_path))
                if exit_code:
                    logger.error('Not able to extract the application tar package')
                    return exit_code

    @staticmethod
    def extract_gmm_data(gmm_app_tar: str):
        """ Extract out all the files from the exported gmm app details tar """
        logger.info("Extracting the gmm-data tar file...")
        # Get the gmm-data tar package
        try:
            gmm_data_dir = os.path.join(os.environ['APP_MIGRATION_DATA_DIR'])
        except KeyError as e:
            # logger.log(str(e) + " is non-existent")
            gmm_data_dir = os.path.abspath('./archive')

        logger.info(f"App Migration Data Directory: {gmm_data_dir}")
        safe_makedirs(gmm_data_dir)
        logger.info('Executing the command: tar -xzvf {0} -C {1}'.format(gmm_app_tar, gmm_data_dir))
        exit_code = os.system('tar -xzvf {0} -C {1}'.format(gmm_app_tar, gmm_data_dir))
        if exit_code:
            logger.error(f"Error occurred on extracting the gmm-data tar file: {gmm_data_dir}")
            raise Exception("File Extract error!")

    def read_app_config(self, app_config_file: str, device_id: str, application: Application):
        """ Read the app config ini file and build a json and return that config payload """
        config_handler = ConfigParser()
        config_data = {}
        try:
            with open(app_config_file, 'r'):
                logger.info('Application config file founded..')
                logger.info(f"Reading the app config file {app_config_file}")
                config_handler.read(app_config_file)
                for section in config_handler.sections():
                    config_data[section] = {}
                    for option in config_handler.options(section):
                        config_data[section][option] = config_handler.get(section, option)
        except FileNotFoundError as e:
            logger.warning("App config file doesn't exists!")
            logger.warning(traceback.format_exc())
            if application:
                logger.info(f"Extracting app config for the app {application.gmm_formatted_app_name}")
                app_details = self.api.get_app_details_from_device(device_id, application.app_id,
                                                                   application.app_version)
                if app_details:
                    config_data = app_details.get('operationalConfiguration', {})
        except RequestException as err:
            logger.warning(f"Exception happened during fetching the app details for "
                           f"the app {application.gmm_formatted_app_name} from the device")
            logger.exception(traceback.format_exc())
        except IOError as e:
            logger.warning("Not able to read the application config file!")
            logger.warning(traceback.format_exc())
        if len(config_data) == 0:
            logger.warning(f"No application config found for the app {application.gmm_formatted_app_name}")
        return config_data

    def build_deploy_payload(self, resource, policy, app_config_data={}, start_app=True):
        policy.update({
            "_valid": True,
            "_childScope": "$SCOPE",
            "givenName": "FogDirectorDefaultPolicy",
            "isNewPlan": True,
            "text": "Install now. If it fails, retry upto 3 times, with at least 5 minutes between retries.",
            "type": "now",
            "invalidReason": ""
        })
        deploy_payload = {
            "deploy": {
                "config": app_config_data,
                "metricsPollingFrequency": 120000,
                "appDataInfo": {
                    "filePaths": [],
                    "fileNames": []
                },
                "tags": [],
                "startApp": start_app,
                "devices": [
                    {
                        "deviceId": self.device.device_id,
                        "resourceAsk": {
                            "resources": resource,
                            "startup": {
                                "runtime_options": "--rm"
                            }
                        }
                    }
                ]
            },
            "policy": policy
        }
        return deploy_payload

    def build_undeploy_payload(self, policy):
        policy.update({
            "_valid": True,
            "_childScope": "$SCOPE",
            "givenName": "FogDirectorDefaultPolicy",
            "isNewPlan": False,
            "text": "Uninstall App now. If it fails, retry upto 3 times, with at least 5 minutes between retries.",
            "type": "now",
            "invalidReason": ""
        })
        deploy_payload = {
            "undeploy": {
                "devices": [
                    self.device.device_id
                ]
            },
            "policy": policy
        }
        return deploy_payload

    def get_app_operational_status(self, app):
        response = {}
        try:
            logger.info(f"Finding operational status for the app {app.app_name}")
            if self.device:
                response = self.api.get_app_details_from_device(self.device.device_id, app.imported_app_id,
                                                                app.app_version)
        except RequestException:
            logger.error(f"HTTP request error happened while trying to get operational status of the app with app id"
                         f"{app.app_name}")
        except Exception as err:
            logger.error(f"Some error occurred while trying to fetch operational status for the app id {app.app_name}")
        return response

    def export_app_with_iox(self):
        """ Exporting an application from GMM with it's app-data and app-config"""
        for device in self.devices:
            for app in device.applications:
                self.ioxclient.ssh_client = self.ioxclient.connection
                try:
                    app_data_dir = os.path.join(os.environ['APP_MIGRATION_DATA_DIR'], app.app_name)
                except KeyError as e:
                    # logger.log(str(e) + " is non-existent")
                    app_data_dir = os.path.abspath(os.path.join('./archive/apps', app.app_name))
                output_path = os.path.join('archive/apps', app.app_name)
                remote_path = self.ioxclient.set_working_dir(app.app_name)
                # Export application tar by calling the IOX-Proxy or FD API
                app.exported_package_name = str(app.gmm_formatted_app_name).join('.' + app.app_version).replace('.', '_')
                self.ioxclient.activate_profile(device.profile_name)
                # Export app-config file
                self.ioxclient.download_app_config(app.gmm_formatted_app_name)
                app.app_config_file_name = 'package_config.ini'
                self.ioxclient.download_file(f'{remote_path}/{app.app_config_file_name}', output_path)
                # Export app-data
                self.ioxclient.download_app_data(app.gmm_formatted_app_name)
                app.app_data_file_name = str(app.gmm_formatted_app_name).join('-datamount.tar.gz')
                self.ioxclient.download_file(f'{remote_path}/{app.app_data_file_name}', output_path)
                self.ioxclient.clear_working_dir(app.app_name)
                self.ioxclient.disconnect()

    def export_app_data(self):
        """ Exporting the app data from each unmanaged applications in IOT-OD """
        for app in self.device.applications:
            try:
                app_data_dir = os.path.join(os.environ['APP_MIGRATION_DATA_DIR'], app.app_name)
            except KeyError as e:
                # logger.log(str(e) + " is non-existent")
                app_data_dir = os.path.abspath(os.path.join('./archive/apps', app.app_name))
            try:
                logger.info(f"App Migration Data Directory: {app_data_dir}")
                logger.info(f"Starting app data export for the application {app.gmm_formatted_app_name}...")
                data = self.api.download_app_data(self.device.device_id, app.app_id, app.app_version)
                if data:
                    with open(os.path.join(app_data_dir, app.app_data_file_name), 'wb') as f:
                        f.write(data)
            except IOError as err:
                logger.error("Not able to create app data tar file due to IO error!")
            except Exception as err:
                logger.error("Some error occurred while downloading the app data!")

        pass

    def get_imported_app_id(self, imported_app_name: str):
        """ Get the newly imported application id which can be used when deploy the app

        :param imported_app_name: search with application name in all existing apps

        :return: str
        """
        search_result = self.api.search_app_details(imported_app_name)
        if len(search_result['data']):
            for app in search_result['data']:
                if app['name'] == imported_app_name:
                    return app['appId']

    def find_app_info(self, app_name: str):
        """ Get the managed app details which can be used when deploy the app

        :param app_name: search with application name in all existing apps

        :return: dict
        """
        search_result = self.api.search_app_details(app_name)
        if len(search_result['data']):
            for app in search_result['data']:
                if app['name'] == app_name:
                    return app

    def track_job_status(self, job_id: int):
        """ Poll a job every 5 secs to check the status of the job and return the status.

        :param job_id: a integer job id that need to be traced

        :return: status
        """
        with concurrent.futures.ThreadPoolExecutor() as executor:
            tick = time()
            while int(time() - tick) < self.MAX_TIMEOUT:
                future = executor.submit(self.api.get_job_details, job_id)
                job_details = future.result()
                if job_details['status'] == 'COMPLETED':
                    return job_details['status']
                sleep(10)

        return 'TIMEOUT'

    def track_app_operational_status(self, app: Application, wait_timeout=300):
        """ Poll a job every 5 secs to check the operational status of the applications.

        :param app: an application instance that need to be traced
        :param wait_timeout: maximum wait time for finding operational status

        :return: status
        """
        with concurrent.futures.ThreadPoolExecutor() as executor:
            tick = time()
            while int(time() - tick) < wait_timeout:
                future = executor.submit(self.get_app_operational_status, app)
                app_details = future.result()
                if app_details.get('operationalStatus', 'UNKNOWN') not in ['DEPLOYED', 'UNKNOWN']:
                    if app_details.get('status') != "RUNNING":
                        app.deploy_status_msg = app_details.get('message', '')
                    return app_details.get('status')
                sleep(5)
        app.deploy_status_msg = app_details.get('message', '')
        return 'DEPLOY_FAILED'

    @staticmethod
    def extract_app_data(application: Application):
        """ Extract app data tar file """
        logger.info("Extracting the app-data tar file...")
        # Get the app-data tar package
        try:
            app_data_dir = os.path.join(os.environ['APP_MIGRATION_DATA_DIR'], application.app_name)
        except KeyError as e:
            # logger.log(str(e) + " is non-existent")
            app_data_dir = os.path.abspath(os.path.join('./archive/apps', application.app_name))

        logger.info(f"App Migration Data Directory: {app_data_dir}")
        app_data_tar = os.path.join(app_data_dir, application.app_data_file_name)
        logger.info(f'looking for app-data tar file for application {application.app_name} is {app_data_tar}')
        safe_makedirs(os.path.join(app_data_dir, 'app_data'))
        logger.info('Executing the command: tar -xzvf {0} -C {1}'.format(app_data_tar, os.path.join(app_data_dir,
                                                                                                    'app_data')))
        exit_code = os.system('tar -xzvf {0} -C {1}'.format(app_data_tar, os.path.join(app_data_dir, 'app_data')))
        if exit_code:
            logger.error(f"Error occurred on extracting the app-data tar file: {app_data_tar}")
            raise Exception("File Extract error!")

        logger.info(f"The app-data tar {app_data_tar} has been extracted to {os.path.join(app_data_dir, 'app_data')}")
        return os.path.join(app_data_dir, 'app_data')

    @staticmethod
    def find_app_data_path(app_path: str):
        for dir_path, dir_names, _ in os.walk(app_path):
            for dir_name in dir_names:
                if dir_name == 'appdata':
                    logger.info(f"App-data file path: {dir_path}")
                    return os.path.join(dir_path, dir_name)

    def get_and_format_gmm_config(self, app_detail, app):
        logger.info("Formatting gmm app config to IOx api compatible format...")
        app_config = defaultdict(dict)
        resource_config = dict()
        if 'app_specific_params' in app_detail:
            for config_data in app_detail['app_specific_params']:
                app_config[config_data['section']].update({
                    config_data['key']: config_data['value']
                })
        logger.info(f"Gmm app config has been successfully formatted as bellow: \n {dict(app_config)}")
        logger.info("Formatting gmm resource config to IOx api compatible format...")
        response = self.find_app_info(app.app_name)
        if response:
            app_info = response['descriptor']['app']
            resource_config = app_info.get('resources')
            if 'resources' in app_detail:
                resource_config['profile'] = app_detail['resources'].get('resource_profile',
                                                                         resource_config.get('profile'))
                resource_config['cpu'] = app_detail['resources'].get('resource_cpu', resource_config.get('cpu'))
                resource_config['memory'] = app_detail['resources'].get('resource_memory',
                                                                        resource_config.get('memory'))

                if 'interface_name' in app_detail['resources']:
                    resource_config['interface-name'] = app_detail['resources'].get('interface_name')

                if 'network_name' in app_detail['resources']:
                    resource_config['network-name'] = app_detail['resources'].get('network_name')

                if 'devices' in app_detail['resources']:
                    resource_config['devices'] = app_detail['resources'].get('devices')

                # app interface information only present in application json file
                if 'app_interfaces' in app_detail['resources']:
                    resource_config['network'] = list()
                    for interface in app_detail['resources']['app_interfaces']:
                        resource_config['network'].append({
                            'interface-name': interface.get('interface_name'),
                            'network-name': interface.get('network_name'),
                            'port_map': {
                                'mode': interface['port_map_mode'],
                                'tcp': {port.get('host_port'): port.get('container_port') for port in
                                        interface.get('tcp', [])},
                                'udp': {port.get('host_port'): port.get('container_port') for port in
                                        interface.get('udp', [])}
                            }
                        })

        return dict(app_config), resource_config

    def is_gmm_data_present(self, name, dir_name='devices'):
        # Get the gmm-data tar package
        try:
            gmm_data_dir = os.path.join(os.environ['APP_MIGRATION_DATA_DIR'])
        except KeyError as e:
            # logger.log(str(e) + " is non-existent")
            gmm_data_dir = os.path.abspath('./archive')

        logger.info(f"Gmm Data Files Directory: {os.path.join(gmm_data_dir, 'gmm_app_details')}")
        gmm_data_file_dir = os.path.join(gmm_data_dir, 'gmm_app_details')
        if self.device:
            if name + '.json' in os.listdir(os.path.join(gmm_data_file_dir, dir_name)):
                logger.info(f"Gmm data file found with name {name + '.json'}")
                return True
        return False

    def get_gmm_resource_config_for_app(self, app):
        # Get the gmm-data tar package
        try:
            gmm_data_dir = os.path.join(os.environ['APP_MIGRATION_DATA_DIR'])
        except KeyError as e:
            # logger.log(str(e) + " is non-existent")
            gmm_data_dir = os.path.abspath('./archive')

        logger.info(f"Gmm Data Files Directory: {os.path.join(gmm_data_dir, 'gmm_app_details')}")
        gmm_data_file_dir = os.path.join(gmm_data_dir, 'gmm_app_details')
        gmm_app_detail_file = app.app_name + '_V' + app.app_version.replace('.', '_')
        if not self.is_gmm_data_present(gmm_app_detail_file, dir_name='apps'):
            raise Exception("Gmm data file not found exception")
        with open(os.path.join(gmm_data_file_dir, gmm_app_detail_file + '.json'), 'r') as data_file:
            logger.info("Get the GMM app config and resource config data")
            app_config, resource_config = self.get_and_format_gmm_config(json.load(data_file), app)
            return app_config, resource_config

    def import_app(self, **kwargs):
        """Import the application to iot-od with app-config and app data.

        :return: None
        """
        if self.device is None:
            logger.info(f"As no devices present so stopping migration...")
            return
        if self.device and len(self.device.applications) == 0:
            logger.info(f"There is no application installed in the device with device serial# {self.device.serial_number}")

        # Get the corresponding deice file exported from gmm and return the app-config and resource detail
        if not self.is_gmm_data_present(self.device.serial_number):
            logger.error(f"Device data file from gmm for found for the device serial no. {self.device.serial_number}")
            raise Exception("Device data file json not found")

        # Check and parse device data using GMM exported device installation json file
        try:
            gmm_data_dir = os.path.join(os.environ['APP_MIGRATION_DATA_DIR'], 'gmm_app_details')
        except KeyError as e:
            gmm_data_dir = os.path.join(os.path.abspath('./archive'), 'gmm_app_details')
        gmm_device_dir = os.path.join(gmm_data_dir, 'devices')
        logger.info(f"Gmm exported devices details directory: {gmm_device_dir}")
        with open(os.path.join(gmm_device_dir, f"{self.device.serial_number}.json")) as device_file:
            self.parse_gmm_device_info(json.load(device_file))

        for app in self.device.applications:
            try:
                # Get the app tar package
                try:
                    gmm_data_dir = os.path.join(os.environ['APP_MIGRATION_DATA_DIR'], 'gmm_app_details')
                    app_data_dir = os.path.join(os.environ['APP_MIGRATION_DATA_DIR'], app.app_name)
                except KeyError as e:
                    # logger.warning(str(e) + " is non-existent")
                    gmm_data_dir = os.path.join(os.path.abspath('./archive'), 'gmm_app_details')
                    app_data_dir = os.path.abspath(os.path.join('./archive/apps', app.app_name))
                app_tar_package = os.path.join(app_data_dir, app.import_package_name)
                # app_config_file = os.path.join(app_data_dir, app.app_config_file_name)
                # app_config_data = self.read_app_config(app_config_file, self.device.device_id, app)
                app_config_data, resource_config = app.app_config, app.resource_config if app.resource_config else \
                    self.get_gmm_resource_config_for_app(app)
                app_data_path = None
                try:
                    if not self.skip_data_migration:
                        app_data_extract_path = self.extract_app_data(app)
                        app_data_path = self.find_app_data_path(app_data_extract_path)
                        logger.info(f"Found app-data for the application {app.app_name} in: {app_data_path}")

                except FileExistsError as err:
                    logger.warning(f'Tar file does not exists for the application {app.app_name}')
                    logger.exception(traceback.format_exc())
                except OSError as e:
                    logger.warning(f'App data not found for the application {app.app_name}')
                    logger.exception(traceback.format_exc())

                # response = self.api.upload_app(app.app_type, app_tar_package)
                response = self.find_app_info(app.app_name)
                # Form the payload for deploying the application
                if response:
                    # app_info = response['descriptor']['app']
                    policy = self.api.get_default_policy()
                    if len(policy):
                        policy = policy[0]
                        if app.need_uninstall:
                            logger.info("Unmanaged app is founded in the device.")
                            logger.info("Uninstalling the unmanaged app from device...")
                            undeploy_payload = self.build_undeploy_payload(policy)
                            undeploy_response = self.api.undeploy_app(app.app_id, app.app_version, undeploy_payload)
                            undeploy_status = self.track_job_status(undeploy_response['jobId'])
                            if undeploy_status == 'TIMEOUT':
                                logger.error('Uninstallation timeout error occurred with max time limit of 30 minutes '
                                             f'for the app {app.gmm_formatted_app_name}')
                                app.deploy_status = "Failed"
                                app.deploy_error = "Timeout error happened on uninstall"
                                raise TimeoutError("Timeout error occurred!")
                            logger.info(f'Uninstallation successful for the application {app.gmm_formatted_app_name}')

                        logger.info("Being ready for installation...")
                        deploy_payload = self.build_deploy_payload(resource_config, policy, app_config_data,
                                                                   not self.skip_starting_app)
                        # Get the new imported app id
                        app.imported_app_id = self.get_imported_app_id(app.app_name)
                        deploy_response = self.api.deploy_app(app.imported_app_id, app.app_version, deploy_payload)
                        # track the deployment status
                        deploy_status = self.track_job_status(deploy_response['jobId'])
                        if deploy_status == 'TIMEOUT':
                            logger.error('Deployment timeout error occurred with max time limit of 30 minutes for '
                                         f'the app {app.app_name}')
                            app.deploy_status = "Failed"
                            app.deploy_error = "Timeout error happened on install!"
                            raise TimeoutError("Timeout error occurred!")
                        logger.info(f'Deployment successful for the application {app.app_name}')
                        if not self.skip_data_migration and app_data_path:
                            logger.info(f"Starting data migration for the application {app.app_name}...")
                            logger.info(f"Starting app-data upload for the application {app.app_name}")
                            logger.info(f"App-data file path: {app_data_path}")
                            for dir_path, dir_names, file_names in os.walk(app_data_path):
                                for filename in file_names:
                                    logger.info(f'Uploading the file {os.path.join(dir_path, filename)}..')
                                    file_path = dir_path.replace(app_data_path, './').replace("\\", "/")
                                    self.api.upload_app_data(self.device.device_id, app.imported_app_id, app.app_version,
                                                             os.path.join(dir_path, filename),
                                                             filepath=file_path if file_path != '' else None,
                                                             new_file_name=filename)
                            logger.info(f"App data upload completed for the application {app.app_name}")
                        app.deploy_status = "Passed"
                        app.operational_status = self.track_app_operational_status(app,
                                                                                   wait_timeout=kwargs.get(
                                                                                       'max_wait_time', 300))
                    else:
                        logger.error("No Fog director policy found!")
                        app.deploy_status = "Failed"
                        app.deploy_error = "No Fog director policy found!"
                else:
                    logger.error(f"Application details not found for the app {app.app_name}")
                    app.deploy_status = "Failed"
                    app.deploy_error = f"Managed application not found with the app name {app.app_name}"
                    raise Exception("Import Error")
            except NameError as e:
                logger.error(f"Was not able to import the app with name {app.app_name}")
                app.deploy_status = "Failed"
                app.deploy_error = "Was not able to import the app"
                logger.error(traceback.format_exc())
            except Exception as err:
                logger.error(f"Error occurred on import of the application {app.app_name}")
                logger.error(traceback.format_exc())
                app.deploy_status = "Failed"
                app.deploy_error = f"Error occurred on import of the application {app.app_name}"
                if not self.continue_on_error:
                    raise Exception("Error occurred during application data import! make sure that exported data "
                                    "is present")
        logger.info("Import Finished!")

    def export_gmm_app(self):
        try:
            output_path = os.environ['APP_MIGRATION_DATA_DIR']
            export_data_dir = os.path.join(os.environ['APP_MIGRATION_DATA_DIR'], 'gmm_app_details')
        except KeyError as e:
            # logger.warning(str(e) + " is non-existent")
            output_path = os.path.abspath('./archive')
            export_data_dir = os.path.abspath(os.path.join('./archive', 'gmm_app_details'))

        if os.path.isdir(export_data_dir):
            logger.error("The directory gmm_app_details is already present! Please rename/move/remove the directory "
                         f"and then retry the script")
            raise Exception("`gmm_app_details` Directory already exists! Please rename/move/remove the directory "
                            "and then retry the script")

        safe_makedirs(export_data_dir)
        logger.info("Creating a gmm details directories...")
        gmm_app_dir = os.path.join(export_data_dir, 'apps')
        gmm_device_dir = os.path.join(export_data_dir, 'devices')
        gmm_template_dir = os.path.join(export_data_dir, 'templates')
        gmm_policies_dir = os.path.join(export_data_dir, 'policies')
        safe_makedirs(gmm_app_dir)
        safe_makedirs(gmm_device_dir)
        safe_makedirs(gmm_template_dir)
        safe_makedirs(gmm_policies_dir)
        gmm_app_dict = defaultdict(list)
        response = self.gmm_api.get_gmm_fog_application(self.gmm_org_id)
        if response:
            for fd_app in response['fog_applications']:
                # Generate app details json file for each gmm app
                with open(os.path.join(gmm_app_dir, f'{fd_app["name"]}_V{fd_app["version"].replace(".", "_")}.json'), 'w') as file:
                    logger.info("Writing apps details in a json file...")
                    app_detail = self.gmm_api.get_gmm_fog_app_details(self.gmm_org_id, fd_app['id'])
                    json.dump(app_detail, file)
                    logger.info(f"Apps details has been written in Json file {file.name}")

                logger.info(f"Finding fog installations for app_id {fd_app.get('id', 0)}")
                installations = self.gmm_api.get_gmm_fog_installation(fd_app.get('id', 0))
                for installation in installations['fog_installations']:
                    installation_detail = self.gmm_api.get_gmm_fog_installation_detail(installation.get('id'))
                    gmm_app_dict[installation['gate_way']['uuid']].append(installation_detail)
                    # Save the full app installation details in a json file with device serial number
                    with open(os.path.join(gmm_device_dir,
                                           f'{installation["gate_way"]["uuid"]}.json'),
                              'w') as file:
                        logger.info("Writing app installation details in a json file...")
                        json.dump(gmm_app_dict[installation['gate_way']['uuid']], file)
                        logger.info(f"App installation details has been written in Json file {file.name}")

        # Save GMM apps details in a json file
        with open(os.path.join(export_data_dir, 'gmm_app_details.json'), 'w') as outfile:
            logger.info("Writing GMM apps details in a json file...")
            json.dump(gmm_app_dict, outfile)
            logger.info("GMM apps details has been written in Json file gmm_app_details.json")

        # Get all application templates and save them in json files
        logger.info(f"Finding application templates for the organization {self.gmm_org_id}...")
        gmm_templates = self.gmm_api.get_gmm_templates(self.gmm_org_id)
        if gmm_templates:
            for template in gmm_templates['application_templates']:
                with open(os.path.join(gmm_template_dir, f'template_{template["id"]}.json'), 'w') as outfile:
                    template_detail = self.gmm_api.get_gmm_template_detail(template['id'])
                    json.dump(template_detail, outfile)

        # Get all application deploy policies and save them in json files
        logger.info(f"Finding application policies for the organization {self.gmm_org_id}...")
        gmm_deploy_policies = self.gmm_api.get_gmm_policies(self.gmm_org_id)
        if gmm_deploy_policies:
            for policy in gmm_deploy_policies['application_deploy_policies']:
                with open(os.path.join(gmm_policies_dir, f'policy_{policy["id"]}.json'), 'w') as outfile:
                    policy_detail = self.gmm_api.get_gmm_policy_detail(policy['id'])
                    json.dump(policy_detail, outfile)

        # Create a tar.gz file containing all the dumped Json files
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        tar_file_name = os.path.join(output_path, f'gmm_org_{self.gmm_org_id}_{timestamp}.tar.gz')
        make_tarfile(tar_file_name, export_data_dir)
        logger.info(f"GMM Apps details has been successfully exported in {tar_file_name}")

    def make_app_migration_report(self):
        """ Generate app migration report summary in tabular format on the console

        :return:
        """
        for app in self.device.applications:
            self.migration_report_data.append([self.device.serial_number, app.app_name, app.app_version,
                                               app.operational_status, app.deploy_error + ' ' + app.deploy_status_msg])

    def show_profile(self):
        self.ioxclient.ssh_client = self.ioxclient.connection
        self.ioxclient.show_profile()
        self.ioxclient.disconnect()


def safe_makedirs(*args):
    try:
        return os.makedirs(*args)
    except OSError:
        pass  # Ignore errors; for example if the paths already exist!


def make_tarfile(output_filename, source_dir):
    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))
