# gmm-iotoc-migration
Repository to manage the scripts and tooling to support migration of customers from GMM to IoTOC

#Instruction

1. Update config.yml to use the correct GMM and IoTOC clusters
2. Update constants.py for GMM_AUTH_PAY_LOAD, RAINE_AUTH_PAY_LOAD, and
3. Update GMM_ORGANIZATION_ID with GMM's organization ID you want to migrate
4. Create the root Tenant you want in IoTOC
5. Update RAINE_TENANT_ID with the newly created IoTOC root tenant
6. python org_migration.py
7. Review the migration details and answer 'Y' to continue

# GMM App Migration Steps
## Pre-Migration Manual Steps
1. Update APP_MIGRATION_CONFIG_VARS in config.yml.
2. Create a PATH Environment Variable APP_MIGRATION_DATA_DIR where application data will be exported
3. Upload or import managed app (renamed without org-id) with respect to all unmanaged apps in IOD-OD after device migration
4. Create a csv file which will contain the device serial numbers those have been migrated to IOT-OD and keep the device file in the current working directory
5. Create a virtual environment with python version 3.7 or above.
6. Activate and install python dependency modules.

Your config file `config.yml` should be present in a folder `config` on current working directory

## Creating virtual environment for python 3.7 and environment setup
You should make sure that you have 3.7 installed in your machine. Run bellow command to create a virtual environment 
with 3.7

### In Linux or mac:
```commandline
mkdir venvs
cd venvs
python3 -m venv <virtual-env-name>
```

### In Windows
```commandline
python -m venv <virtual-env-name>
```

**You should make sure that `python` or `python3` interpreter points to python 3.7 installed location.**

Once virtual environment has been created you need to activate the environment and install python dependency modules
### In Linux or mac
```commandline
cd <virtual-env-name>
source bin/activate
```
### In Windows
```commandline
cd <virtual-env-name>
Scripts\activate
```

After activation of the virtual environment you need to switch to the directory where you cloned this project
and install python dependency modules.
```commandline
pip install -r requirements.txt
```
## Running GMM App Details Export
This will export the all the application installed with device details, app config, templates, policies and installation values.
Before running the bellow command make sure that you changed the `config.yml` with proper details and `GMM_ORG_ID` and `GMM_API_KEY` is correct under `APP_MIGRATION_CONFIG_VARS` section.
Or also you can pass this values from command line to override the `config.yml` values.
```commandline
python migrate.py export-gmm-app-details
```

## Running migration for stateless application
For migration of a stateless application run the following command
```commandline
python migrate.py install-gmm-app-to-iod --device-file <device_file_name>.csv <GMM_EXPORTED_TAR>
```

## Running migration for stateful application
For the migration of the stateful applications run the following command
```commandline
python migrate.py install-gmm-app-to-iod --skip-data-import=False --device-file <device_file_name>.csv <GMM_EXPORTED_TAR>
```

## Help for app migration command options available
To manage the app migration operation you can use many options available in app migration script. Run the bellow to get the help
```commandline
python migrate.py install-gmm-app-to-iod --help
```

