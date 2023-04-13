from core.config import get_config_data as config
from core.constants import *
from core.http_request_handler import serve_get_request
from core.http_request_handler import serve_post_request
from core.utilities import gmm_access_token
from core.utilities import raine_access_token
from pprint import pprint as pp
from collections import OrderedDict
import json

from logs import log

logger = log.get_logger("GMM Users data :: ")

def get_GMM_org_members(org_id):
    token = gmm_access_token
    if not token:
        logger.error("No access token")
        raise

    AUTH_HEADERS["Authorization"] = token
    base_url = config.gmm_server.get('base_url')
    org_url = config.gmm_server.get("get_organization_members").replace('^', str(org_id))
    url = "{}{}".format(base_url, org_url)
    gmm_members = serve_get_request(url, AUTH_HEADERS)
    if 200 != gmm_members["status"]:
        logger.error('Unable to get members' + gmm_org_id)
        raise

    members = gmm_members["data"]["memberships"]
    gmm_users = [{'email': item['user']['email'],
                  'username': item['user']['name'],
                  'role': "{}-GMM".format(item['role'].upper())
                  } for item in members if item['user']['email'] != 'gwaas-iot@cisco.com']
    return  gmm_users

def get_GMM_org_tree(gmm_org_id, ancestry_depth = 0):
    token = gmm_access_token
    org = OrderedDict()
    if not token:
        logger.error("No access token")
        raise

    AUTH_HEADERS["Authorization"] = token
    base_url = config.gmm_server.get('base_url')

    org_url = config.gmm_server.get("get_organization").replace('^', str(gmm_org_id))
    url = "{}{}".format(base_url, org_url)
    gmm_org = serve_get_request(url, AUTH_HEADERS)
    if 200 != gmm_org['status']:
        logger.error('Unable to read org ' + gmm_org_id)
        raise
    org['name'] = gmm_org['data']['name']
    members = get_GMM_org_members(gmm_org_id)
    org['members'] = members
    org['child_orgs'] = []
    if ancestry_depth < 2:
        # find out more child orgs
        org_url = config.gmm_server.get("get_child_organizations").replace('^', str(gmm_org_id))
        url = "{}{}".format(base_url, org_url)
        gmm_child_orgs = serve_get_request(url, AUTH_HEADERS)
        if 200 == gmm_child_orgs["status"]:
            child_orgs = gmm_child_orgs["data"]["organizations"]
            for child in child_orgs:
                gmm_child_org = get_GMM_org_tree(child['id'], child['ancestry_depth'])
                org['child_orgs'].append(gmm_child_org)
    return org

def get_tenant_roles(tenant_id):
    token = raine_access_token
    if not token:
        logger.error("No access token")
        raise
    AUTH_HEADERS["Authorization"] = token
    AUTH_HEADERS['x-access-token'] = token
    base_url = config.raine_server.get('base_url')
    role_url = config.raine_server.get("get_roles")
    url = "{}{}{}".format(base_url, role_url, tenant_id)
    roles_data = serve_get_request(url, AUTH_HEADERS)
    return roles_data['data']['roles']

def add_tenant_role(tenant_id, name, permissions):
    token = raine_access_token
    if not token:
        logger.error("No access token")
        raise
    AUTH_HEADERS["Authorization"] = token
    AUTH_HEADERS['x-access-token'] = token
    AUTH_HEADERS['x-tenant-id'] = tenant_id
    base_url = config.raine_server.get('base_url')
    role_url = config.raine_server.get("create_roles")
    url = "{}{}".format(base_url, role_url)
    payload = {
        'name' : name,
        'service_name' : 'network-mgmt',
        'permissions' : permissions
    }
    pp(payload)
    new_role = serve_post_request(url, AUTH_HEADERS, payload)
    return new_role['data']['role_uuid']

def add_tenant_users(tenant_id, role_id, users):
    token = raine_access_token
    if not token:
        logger.error("No access token")
        raise
    AUTH_HEADERS['x-access-token'] = token
    AUTH_HEADERS['x-tenant-id'] = tenant_id
    base_url = config.raine_server.get('base_url')
    api_url = config.raine_server.get("create_users")
    url = "{}{}".format(base_url, api_url)
    for i in users:
        print('Adding user "%s"/%s' % (i['username'], i['email']))
        payload = {
            'username': i['email'],
            'email'   : i['email'],
            'roles'   : [{
                'tenant_id': tenant_id,
                'role_id': role_id,
            }]
        }
        pp(payload)
        user_data = serve_post_request(url, AUTH_HEADERS, payload)

def migrate_GMM_orgs(gmm_orgs, tenant_id):
    token = raine_access_token
    if not token:
        logger.error("No access token")
        raise
    AUTH_HEADERS["Authorization"] = token
    AUTH_HEADERS['x-access-token'] = token
    AUTH_HEADERS["x-tenant-id"] = tenant_id
    base_url = config.raine_server.get('base_url')
    tenant_url = config.raine_server.get("create_tenants")
    url = "{}{}".format(base_url, tenant_url)

    roles = get_tenant_roles(tenant_id)
    devop_role = next((i for i in roles if i['name'] == 'Device Operator'), None)
    admin_users = [i for i in gmm_orgs['members'] if i['role'] == 'ADMIN-GMM']
    if admin_users:
        if not devop_role:
            logger.error('No Device Operator Role in Tenant!!!')
            exit()
        add_tenant_users(tenant_id, devop_role['id'], admin_users)

    r_op_role =  next((i for i in roles if i['name'] == 'Restricted Operator'), None)
    if r_op_role:
        r_op_role_id = r_op_role['id']
    else:
        # create Restricted Operator
        view_dev_permission = next((i for i in devop_role['permissions'] if i['name'] == 'View Devices'))
        r_op_role_id = add_tenant_role(tenant_id, 'Restricted Operator', [view_dev_permission])

    oper_users = [i for i in gmm_orgs['members'] if i['role'] == 'OPERATOR-GMM']
    if oper_users:
        add_tenant_users(tenant_id, r_op_role_id, oper_users)

    for org in gmm_orgs['child_orgs']:
        print('Creating Child Org ' + org['name'])
        pay_load_tenant = {
            "name": org['name'],
            "description": "",
            #"admins": [],
            "services": [
                {"uuid": RAINIER_DM_SERVICE_UUID,
                 "name": RAINIER_DM_SERVICE_NAME,
                 "display_name": "Edge Device Manager",
                 "description": "Manage your network of devices.",
                 "enabled": True}]
        }
        AUTH_HEADERS["Authorization"] = token
        AUTH_HEADERS["x-tenant-id"] = tenant_id
        r = serve_post_request(url, AUTH_HEADERS, pay_load_tenant)
        if 200 != r["status"]:
            logger.error('Error Creating Child org')
            exit()
        new_tenant_id = r["data"]['tenant_uuid']
        migrate_GMM_orgs(org, new_tenant_id)

        print('Child Org ' + org['name'] + ' Migrated')


gmm_orgs = get_GMM_org_tree(GMM_ORGANIZATION_ID)
print('GMM Org to migrate:')
print(json.dumps(gmm_orgs, indent=4))
ans = raw_input('Migrate GMM org %s and all its sub-orgs(Y/N)? ' % gmm_orgs['name'])
if ans.upper() != 'Y':
    print("User Aborted.")
    exit()
print("Migration in Progess...")
migrate_GMM_orgs(gmm_orgs, RAINE_TENANT_ID)
