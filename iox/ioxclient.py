import uuid
import logging
import subprocess
import sys
import os
from typing import List
from paramiko import SSHClient, AutoAddPolicy, RSAKey
from paramiko.auth_handler import AuthenticationException, SSHException
from scp import SCPClient, SCPException


logging.basicConfig(stream=sys.stdout, level=logging.INFO)


class Profile:
    def __init__(self, name: str, host: str, port: str, auth_keys: str, auth_token: str, api_prefix: str,
                 url_schema: str, rsa_key: str, certificate: str, is_active: bool):
        self.name = name
        self.host = host
        self.port = port
        self.auth_keys = auth_keys
        self.auth_token = auth_token
        self.api_prefix = api_prefix
        self.url_schema = url_schema
        self.rsa_key = rsa_key
        self.certificate = certificate
        self.is_active = is_active


class IOXClient:
    """
    IOXClient is a remote host from we should able to reach all the devices in the network
    """
    def __init__(self, host: str, any_connect: bool, iox_user: str, iox_password: str, ssh_key_path: str,
                 remote_path='~/', local_data_path='archive', platform="linux", version="1.13.0.0"):
        self.version = version
        self.profiles = []
        self.session_id = str(uuid.uuid4())
        self.host = host
        self.any_connect = any_connect
        self.iox_user = iox_user
        self.iox_password = iox_password
        self.ssh_key_path = ssh_key_path
        self.remote_path = remote_path
        self.local_data_path = local_data_path
        self.ssh_client = None
        self.user_platform = platform
        self.logger = logging.getLogger("IOXClient.logger")
        self.paramiko_logger = logging.getLogger("paramiko.logger")
        if self.any_connect:
            self._check_and_connect_vpn()
        # self._get_ssh_key()
        # self._upload_ssh_key()

    def _check_and_connect_vpn(self):
        """ Check and ensure that the user is connected to right network """
        try:
            app_data_dir = os.path.join(os.environ['APP_MIGRATION_DATA_DIR'])
        except KeyError as e:
            # logger.log(str(e) + " is non-existent")
            app_data_dir = os.path.abspath(os.path.join('./archive'))
        try:
            any_connect_file = os.path.join(app_data_dir, 'anyconnect.txt')
            logging.info("Closing all existing vpn connections...")
            os.system("vpncli disconnect") if self.user_platform == "windows" else \
                os.system("/opt/cisco/anyconnect/bin/vpn disconnect")

            cmd_result = os.system("vpncli -s < %s" % any_connect_file) if self.user_platform == 'windows' else \
                os.system("/opt/cisco/anyconnect/bin/vpn -s < %s" % any_connect_file)

            if cmd_result:
                logging.error("Not able connect the vpn network!")
                raise Exception("VPN Connection Failed")

            logging.info("VPN connection has been successfully established")

        except Exception as e:
            self.logger.warning("Please chek that cisco any-connect vpn is installed and added to the path!")
            self.logger.error(e)
            raise e

    def _get_ssh_key(self):
        """
        Get locally stored ssh key
        """
        try:
            self.ssh_key = RSAKey.from_private_key(self.ssh_key_path)
            self.paramiko_logger.info(f"Found ssh key at {self.ssh_key_path}")
            return self.ssh_key
        except SSHException as e:
            self.paramiko_logger.error(e)

    def _upload_ssh_key(self):
        """
        Upload the ssh key to the remote iox client machine
        """
        if self.user_platform == 'windows':
            os.system(f"type $env:USERPROFILE\.ssh\id_rsa.pub | ssh {self.iox_user}@{self.host} \"cat >> .ssh/authorized_keys\"")
        else:
            os.system(f"ssh-copy-id -i {self.ssh_key_path}.pub {self.iox_user}@{self.host}>/dev/null 2>&1")

    @property
    def connection(self):
        """ Open connection to remote IOXClient host """
        try:
            self.ssh_client = SSHClient()
            self.ssh_client.load_system_host_keys()
            self.ssh_client.set_missing_host_key_policy(AutoAddPolicy)
            self.ssh_client.connect(self.host, username=self.iox_user, password=self.iox_password,
                                    key_filename=self.ssh_key_path, timeout=10000)
            return self.ssh_client
        except AuthenticationException as e:
            self.paramiko_logger.error(f'Authentication failed: did you remember to create an ssh key? {e}')
            raise e

    @property
    def scp(self) -> SCPClient:
        conn = self.connection
        return SCPClient(conn.get_transport())

    def disconnect(self):
        """ Close ssh connection """
        if self.ssh_client:
            self.ssh_client.close()
        if self.scp:
            self.scp.close()

    def set_working_dir(self, app_name: str):
        """ Set the working directory in IOX-Client Remote """
        self.execute_commands(["mkdir -p " + app_name, "cd " + app_name])
        self.remote_path = "~/" + app_name
        return self.remote_path

    def clear_working_dir(self, app_name: str):
        """ Once data transfer is done working directory should be cleaned"""
        self.execute_commands(["cd ~", "rm -rf " + app_name])

    def bulk_upload(self, files: List[str]):
        """
        Upload multiple files to a remote directory.

        :param files: List of local files to be uploaded.
        :type files: List[str]
        """
        try:
            self.scp.put(files, remote_path=self.remote_path)
            self.paramiko_logger.info(f"Finished uploading {len(files)} files to {self.remote_path} on {self.host}")
        except SCPException as e:
            raise e

    def download_file(self, file: str, local_path):
        """Download file from remote host."""
        self.scp.get(file, local_path=local_path)

    def execute_commands(self, commands: List[str]):
        """
        Execute multiple commands in succession.

        :param commands: List of unix commands as strings.
        :type commands: List[str]
        """
        for cmd in commands:
            stdin, stdout, stderr = self.ssh_client.exec_command(cmd)
            stdout.channel.recv_exit_status()
            response = stdout.readlines()
            for line in response:
                self.logger.info(f"INPUT: {cmd} | OUTPUT: {line}")

    def execute_local_command(self, module, command, option=None, *args):
        self.logger.info(f"Executing Command: {module} {command}")

        cmd_result_obj = subprocess.run([module, command, " ".join(args)], stdout=subprocess.PIPE,
                                        text=True, check=True) if not option else subprocess.run([module,
                                                                                                  command, "--"+option,
                                                                                                  " ".join(args)],
                                                                                                 stdout=subprocess.PIPE,
                                                                                                 text=True, check=True)
        self.logger.info(cmd_result_obj.stdout) if cmd_result_obj.returncode == 0 else \
            self.logger.error(cmd_result_obj.stderr)

        return cmd_result_obj

    def show_profile(self):
        self.execute_commands(["ioxclient profiles show"])

    def activate_profile(self, profile_name):
        self.execute_commands(["ioxclient profiles activate " + profile_name])

    def download_app_config(self, app_id):
        self.execute_commands(["ioxclient app getconfig " + app_id])

    def download_app_data(self, app_id):
        self.execute_commands(["ioxclient app datamount download " + app_id])