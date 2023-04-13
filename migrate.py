import csv
import sys
import os
import argparse
import traceback
from tabulate import tabulate
import click

from app_migration import AppMigration
from core.config import get_config_data as config
from logs import log

logger = log.get_logger("Migrate::")

parser = argparse.ArgumentParser(description="Gmm App Migration")
parser.add_argument('--device_file', type=str, required=True, help='Device File')


def read_device_csv(device_file, **kwargs):
    devices = []
    with open(device_file) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0
        for row in csv_reader:
            if line_count == 0:
                logger.info(f'Column names are {", ".join(row)}')
                line_count += 1
            else:
                device_details = {}
                logger.info(f'\tFound device IP{row[0]} with device name {row[1]}')
                device_details['device_ip'] = row[0] if row[0] != "" else None
                device_details['port'] = row[1] if row[1] != "" else None
                device_details['serial_number'] = row[2] if row[2] != "" else None
                device_details['network_ip'] = row[3] if row[3] != "" else None
                device_details['network_grp'] = row[4] if row[4] != "" else None
                device_details['skip_vpn_trust'] = row[5] if row[5] != "" else 'n'
                device_details['vpn_user'] = row[6] if row[6] != "" else None
                device_details['vpn_pwd'] = row[7] if row[7] != "" else None
                devices.append(device_details)

                line_count += 1
                print(f'Processed {line_count} lines.')
        return devices


def read_device_serial_no(device_file, **kwargs):
    devices = []
    with open(device_file) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0
        for row in csv_reader:
            if line_count == 0:
                logger.info(f'Column names are {", ".join(row)}')
                line_count += 1
            else:
                device_details = {}
                logger.info(f'\tFound device Serial {row[0]}')
                device_details['device_ip'] = None
                device_details['port'] = None
                device_details['serial_number'] = row[0] if row[0] != "" else None
                device_details['network_ip'] = None
                device_details['network_grp'] = None
                device_details['skip_vpn_trust'] = 'n'
                device_details['vpn_user'] = None
                device_details['vpn_pwd'] = None
                devices.append(device_details)

                line_count += 1
                print(f'Processed {line_count} lines.')
        return devices


@click.group('migrate')
def migrate():
    # args, sys.argv[1:] = parser.parse_known_args(sys.argv[1:])
    # device_file = args.device_file
    pass

# *********************** Command Line Utility For App Migration ************************ #


@migrate.command('install-gmm-app-to-iod', short_help='install applications on batch of devices after'
                                                      ' device migration is done')
@click.option('-auth', '--auth-type', default=config.app_migration_vars.get('auth_type'), type=str,
              help='Authentication can be done using FOGD API or Rainier For Rainier you should type `Rainier` here, '
                   'default value is `Basic`')
@click.option('-ssl', '--ssl-verify', default=False, type=bool,
              help='ssl_verify should be always true for production cluster, '
              'if using local cluster without ca certificate then '
              'this should be set to `False`')
@click.option('-p', '--platform', default=config.app_migration_vars.get('platform'), type=str,
              help='If running from windows, set this option to `windows`')
@click.option('-ignore_error', '--continue-on-error', default=os.getenv('continue_on_error', False), type=bool,
              help='Set this to True if want to ignore errors')
@click.option('-skip_app_data', '--skip-data-import', default=os.getenv('skip_data_import', True), type=bool,
              help='Set this option to False if you want to import data '
                   'for installed apps and also make sure that you have '
                   'exported data ready in the ENVIRONMENT PATH VAR '
                   'APP_MIGRATION_DATA_DIR')
@click.option('-skip_app_start', '--skip-starting-app', default=os.getenv('skip_starting_app', False), type=bool,
              help='Set this to True if do not want to start the app '
                   'after migration')
@click.option('-skip_managed_app', '--skip-managed-app', default=os.getenv('skip_managed_app', True), type=bool,
              help='Set this to False if want to do migration for managed app as well')
@click.option('-device_file', '--device-file', default=os.getenv('device_file'), type=click.STRING,
              help='Give the device file if you want to install apps only for specific set of devices')
@click.option('-wait_time', '--max-wait-time', default=300, type=int,
              help='Set the maximum wait time in seconds if any request taking time to fetch the response, '
                   'default is 300 secs')
@click.argument('gmm_export_tar', type=click.Path(exists=True), required=True)
def migrate_gmm_app(auth_type, ssl_verify, platform, continue_on_error, skip_data_import, skip_starting_app,
                    skip_managed_app, device_file, max_wait_time, gmm_export_tar):
    """
    This command will do install all the applications which were previously installed on the given devices in GMM.
    This command needs the output of export-gmm-app-details command. This command should be executed once the selected
    devices have been migrated from GMM to IOT-OD.

    Please make sure that you have uploaded all required application versions into IOT-OD app management.
    If an application version which was present in GMM is not uploaded into IOT-OD the same would not be installed back
    on to the devices by this command.

    Example:

        python migrate.py install-gmm-app-to-iod --device-file=device_file_test.csv ./archive/gmm_org_2414.tar.gz

    """
    app_migration = AppMigration(iox_client_host=config.app_migration_vars.get('iox_client_host'),
                                 iox_user=config.app_migration_vars.get('iox_user'),
                                 iox_password=config.app_migration_vars.get('iox_password'),
                                 ssh_key_path=config.app_migration_vars.get('ssh_key_path'),
                                 api_server=config.app_migration_vars.get('base_url'),
                                 port=config.app_migration_vars.get('port'),
                                 api_user=config.app_migration_vars.get('api_user'),
                                 api_password=config.app_migration_vars.get('api_password'),
                                 api_prefix=config.app_migration_vars.get('api_prefix'),
                                 auth_type=os.getenv('auth_type', auth_type),
                                 platform=os.getenv('platform', platform),
                                 ssl_verify=os.getenv('ssl_verify', ssl_verify),
                                 continue_on_error=continue_on_error,
                                 skip_data_migration=skip_data_import,
                                 skip_starting_app=skip_starting_app,
                                 skip_managed_apps=skip_managed_app,
                                 gmm_api_server=config.gmm_server.get('base_url'),
                                 gmm_api_key=config.app_migration_vars.get('GMM_API_KEY'),
                                 gmm_org_id=config.app_migration_vars.get('GMM_ORG_ID'))
    # Extract gmm data tar file
    app_migration.extract_gmm_data(gmm_export_tar)

    if device_file and device_file != "":
        logger.info(f"Found device file with name {device_file}")
        devices = read_device_serial_no(device_file)

    else:
        logger.info("Device file not found! Calling the device api to find the migrated devices...")
        devices = app_migration.get_migrated_gmm_devices()

    for device_detail in devices:
        try:
            logger.info(f"Starting app import for device with serial number {device_detail.get('serial_number')}...")
            if device_file and device_file != "":
                app_migration.network_ip = device_detail.get('network_ip')
                app_migration.network_grp = device_detail.get('network_grp')
                app_migration.skip_vpn_trust = device_detail.get('skip_vpn_trust')
                app_migration.vpn_user = device_detail.get('vpn_user')
                app_migration.vpn_pwd = device_detail.get('vpn_pwd')

                # app_migration.import_app('iox_app.tar', 'iox_app.ini', './')
                # app_migration.show_profile()
                app_migration.get_target_device_details(device_ip=device_detail.get('device_ip'),
                                                        profile_name=config.app_migration_vars.get('iox_profile_name'),
                                                        port=device_detail.get('port'),
                                                        serial_number=device_detail.get('serial_number'))
            else:
                app_migration.parse_device_info(device_detail,
                                                profile_name=config.app_migration_vars.get('iox_profile_name'))
            if not app_migration.skip_data_migration:
                app_migration.export_app_data()

            logger.debug(f"Skip_data_import: {app_migration.skip_data_migration}\n "
                         f"skip_managed_app : {app_migration.skip_managed_apps}\n "
                         f"continue_on_error : {app_migration.continue_on_error}\n "
                         f"skip_starting_app : {app_migration.skip_starting_app}")
            app_migration.import_app(max_wait_time=max_wait_time)
            logger.info(f"End import for device with serial number {device_detail.get('serial_number')}")
        except NameError as err:
            logger.error(traceback.format_exc())
        except Exception as exp:
            logger.error(traceback.format_exc())
        finally:
            if app_migration.device:
                app_migration.make_app_migration_report()

    logger.info("Finished application import for all devices!\n")
    print("****************** Summary ******************\n")
    report_header = ['Device Serial#', 'App Name', 'App Version', 'App Status', 'Error']
    print(tabulate(app_migration.migration_report_data, report_header, tablefmt="pretty"))


@migrate.command('export-gmm-app-details', short_help='Export all applications details with their configurations from GMM')
@click.option('-url', '--base-url', default=config.gmm_server.get('base_url'), type=str,
              help='GMM api url')
@click.option('-org', '--org-id', default=config.app_migration_vars.get('GMM_ORG_ID'), type=int,
              help='GMM Organization ID')
@click.option('-key', '--api-key', default=config.app_migration_vars.get('GMM_API_KEY'), type=str,
              help='GMM Api Access Key')
def export_gmm_app_details(base_url, org_id, api_key):
    """
    This command will export all applications details from the given GMM organization. Exported data includes the
    uploaded application details, details of applications installed on devices, templates and policies. This details
    will be exported as a tar.gz file.

    This file can serve as a reference for application information in GMM.

    If you want to change configuration values or resource values, then you can modify the <serial_number>.json file
    under device folder and then recreate a new tar.gz with modified files. Then you can use the modified tar.gz file as
    input argument of install-gmm-app-to-iod command.

    Use this command to export the application details before you start the device migration process so that you have
    reference of original GMM configuration.

    Example:

        python migrate.py export-gmm-app-details --base-url=https://jokerdev.iotspdev.io/api/v2/ --org-id=2766 --api-key=435535ghsh

    """
    app_migration = AppMigration(iox_client_host=config.app_migration_vars.get('iox_client_host'),
                                 iox_user=config.app_migration_vars.get('iox_user'),
                                 iox_password=config.app_migration_vars.get('iox_password'),
                                 ssh_key_path=config.app_migration_vars.get('ssh_key_path'),
                                 api_server=config.app_migration_vars.get('base_url'),
                                 port=config.app_migration_vars.get('port'),
                                 api_user=config.app_migration_vars.get('api_user'),
                                 api_password=config.app_migration_vars.get('api_password'),
                                 api_prefix=config.app_migration_vars.get('api_prefix'),
                                 auth_type=os.getenv('auth_type', 'GMM'),
                                 platform=os.getenv('platform', 'linux'),
                                 ssl_verify=os.getenv('ssl_verify', True),
                                 gmm_api_server=base_url,
                                 gmm_api_key=api_key,
                                 gmm_org_id=org_id)
    app_migration.export_gmm_app()
    pass

# *************************************************************************************** #


if __name__ == '__main__':
    migrate()
