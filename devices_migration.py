from core.config import get_config_data as config
from core.constants import *
from core.http_request_handler import serve_get_request
from core.http_request_handler import serve_post_request
from core.utilities import gmm_access_token
from pprint import pprint as pp
from collections import OrderedDict
import json
import csv
from pygments import highlight, lexers, formatters
from logs import log
from core.gateway_config import *
import os

file_name = 'devices.csv'
logger = log.get_logger("GMM Gateway data :: ")

def check_file_exists(file_name):
    return

def append_list_as_row(file_name, list_of_elem):
    heading_exists = check_if_heading_exists(file_name)
    if heading_exists == False:
        # Open file in append mode
        with open(file_name, 'a') as write_obj:
            # Create a writer object from csv module
            csv_writer = csv.writer(write_obj)
            # Add contents of list as last row in the csv file
            csv_writer.writerow(list_of_elem)

def check_if_heading_exists(file_name):
    if os.path.exists(file_name):
        if(os.stat(file_name).st_size == 0):
            # Open file in append mode
            with open(file_name, 'r') as csvfile:
                spamreader = csv.reader(csvfile, delimiter=',')
                for row in spamreader:
                    if(row[0] == 'name' and row[1] == 'eid'):
                        return True
                    else:
                        return False
    return False

def get_GMM_gateway_cfg(gmm_org_id):
   # Get Token
    token = gmm_access_token
    if not token:
        logger.error("No access token")
        exit()

    AUTH_HEADERS["Authorization"] = token
    base_url = config.gmm_server.get('base_url')

    offset = 0
    limit = 100
    org_url = config.gmm_server.get("get_gateway_params").replace('^', str(gmm_org_id))
    output = []
    while True:
        url = "{}{}?offset={}&limit={}".format(base_url, org_url, str(offset), str(limit))
        response = serve_get_request(url, AUTH_HEADERS)
        if 200 != response['status']:
            logger.error('Unable to read org ' + str(gmm_org_id))
            exit()
        else:
            output.extend(response['data']['gate_ways'])
            pages = response['data']['paging']['pages']
            if offset < (pages * limit):
                offset = offset + limit
            else:
                break
            # formatted_json = json.dumps(output, indent=4)
            # colorful_json = highlight(unicode(formatted_json, 'UTF-8'), lexers.JsonLexer(), formatters.TerminalFormatter())
            # print(colorful_json)
    return output


# Main function
gtwCfg = get_GMM_gateway_cfg(GMM_ORGANIZATION_ID)

if gtwCfg is not None:
    # Add first Row headings
    append_list_as_row(file_name,gtwCfgMap.values())

    for item in gtwCfg:
        tmp_list = list()
        tmp_list.append(item['name'])
        tmp_list.append(item['model']+'+'+item['uuid'])
        if 'IR8' in item['model']:
            tmp_list.append('ir800')
            tmp_list.append('default-ir800')
        elif 'IR11' in item['model']:
            tmp_list.append('ir1100')
            tmp_list.append('default-ir1100')

        # Get Nested Config
        nested_gateway_cfg = item['gateway_config']
        for key,value in gtwCfgMap.items():
            if key in nested_gateway_cfg:
                tmp_list.append(nested_gateway_cfg[key])

        #Add to CSV
        append_list_as_row(file_name, tmp_list)
