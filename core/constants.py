GMM_AUTH_PAY_LOAD = {
  'email': 'xxxxxx@cisco.com',
  'password': 'xxxxxxx',
  'otp': ''
}

RAINE_AUTH_PAY_LOAD = {
  'username': 'xxxxxx@cisco.com',
  'password': 'xxxxxxx'
}

GMM_AUTH_TOKEN = "Token xxxxxxx"

GMM_ORGANIZATION_ID = 0000

RAINE_TENANT_ID = 'xxxxxx'

# =========================================== #
# constants below ideally need not be modifed #
# =========================================== #

MIME_TYPE = 'application/json'
MAX_RETRIES = 10

AUTH_HEADERS = {
    'Content-type':  MIME_TYPE,
    'Accept': MIME_TYPE,
    'Authorization': '',
}

GMM_ROLES = ['Operator', 'Admin']

RAINE_SERVICE_NAME = 'system-mgmt'

RAINIER_DM_SERVICE_NAME = 'network-mgmt'

RAINIER_DM_SERVICE_UUID = '989cf627-c94a-4383-a83a-e2504f7c8137'

RAINE_ADMIN_ROLE_ID = '6883eaa9-7c30-45c8-a9fc-94187aefffbe'

RAINE_OPERATOR_ROLE_ID = 'e4ccef1a-cb80-4693-95f2-e11e722ee200'

RAINE_ADMIN_PERMISSIONS = [
         {
            'id': 'b88defaa-cb69-470c-9c0c-2788ea42a9d7',
         },
         {
            'id': 'e6b2de99-968e-45ff-b989-ee8eb82266fb',
         },
         {
            'id': 'ab576dd4-4f60-4a49-94b8-b97c97db83e8',
         },
         {
            'id': '69bf1714-d1df-4576-91a9-3d9cd6f24133',
         }
      ]

RAINE_OPERATOR_PERMISSIONS = [
         {
            'id': '5261dd40-750b-4728-b5f1-ff479a38ac93',

         },
         {
            'id': '195a26e1-87d0-4657-a508-4921cec2abe7',

         },
         {
            'id': '1d6fa5bc-a47b-4972-a81d-889522f341ad',

         },
         {
            'id': '5774726d-9e6d-469f-8274-77b893a7f66c',
         },
         {
            'id': 'ae8b15d0-e909-483a-8f33-549f56ac6a60',
         },
         {
            'id': 'a4461947-088a-4f41-8df7-fed61b5daa9e',
         }
   ]

# root tenant
#RAINE_TENANT_ID = '61685eca-24ce-4cfb-9828-56c644cecb3c'

RAINE_PERMISSIONS = {
                    "ADMIN-GMM":  RAINE_ADMIN_PERMISSIONS,
                    "OPERATOR-GMM": RAINE_OPERATOR_PERMISSIONS,
}
RAINE_USER_CREDENTIALS = {
                    "ADMIN-GMM":  RAINE_ADMIN_ROLE_ID,
                    "OPERATOR-GMM": RAINE_OPERATOR_ROLE_ID,
}

# RAINE_PARENT_ID = '39122305-5a91-4f23-ab1c-845a185ddeb8'
# RAINE_OWNER_TENANT_ID= '61685eca-24ce-4cfb-9828-56c644cecb3c'
# SOURCE_BASE_URL ='https://cyclops.iotspdev.io/api/v2/'
# DESTINATION_BASE_URL = 'https://RAINErbts1.ciscoiotdev.io/iam/'
# GMM_ORGANIZATION_ID = 5
#
# SOURCE_AUTH_URL = '{}users/access_token'.format(SOURCE_BASE_URL)
# SOURCE_ORGANIZATION_MEMBERS= '{}organizations/{}/memberships'.format(SOURCE_BASE_URL,GMM_ORGANIZATION_ID)
#
# DESTINATION_AUTH_URL = '{}auth/token'.format(DESTINATION_BASE_URL)
# DESTINATION_ROLES_URL= '{}roles?x-tenant-id={}'.format(DESTINATION_BASE_URL,RAINE_TENANT_ID)
# DESTINATION_CREATE_ROLE_URL = '{}roles'.format(DESTINATION_BASE_URL)
# DESTINATION_CREATE_USER_URL= '{}users'.format(DESTINATION_BASE_URL)
