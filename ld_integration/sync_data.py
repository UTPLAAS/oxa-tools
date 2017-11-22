"""

Course consumption syncronization between OXA and  L&D

"""
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
import configparser

import ld_integration

CONFIG = configparser.ConfigParser()
CONFIG.read('oxa_ld_config.cfg')
#TODO: read file from the known path

#pylint: disable=line-too-long

def sync_edx_data(integration_type):
    """

    1) GET access token from Azure tenant using MSI
    2) GET secrets from Azure keyvault using the access token
    3) GET the Course catalog data from OpenEdx using the secrets obtined from Azure key vault
    4) Map and process the OpenEdx course catalog data with L&D Catalog Consumption API request body
    5) POST the mapped data to L&D based on the parameter.

    """
    log_file_name = '{0}.log'.format(integration_type)
    logging.basicConfig(filename=log_file_name, format='%(asctime)s - %(name)s - %(levelname)s', level=logging.INFO)
    log = logging.getLogger(__name__)
    handler = logging.handlers.TimedRotatingFileHandler(log_file_name, when="d", interval=1, backupCount=10)
    log.addHandler(handler)
    log.info("Starting the Course %s Interation process", integration_type)

    # initialize the key variables
    catalog_service = ld_integration.EdxIntegration(logger=log)

    secret_keys_dict = {}
    attempts = 0

    while attempts < int(CONFIG.get('general', 'retry_count')):
        try:

            for azure_key_vault_key in CONFIG.get('azure_key_vault', 'azure_key_vault_keys').split('\n'):
                # get secrets from Azure Key Vault
                secret_keys_dict[azure_key_vault_key] = catalog_service.get_key_vault_secret(catalog_service.get_access_token(), CONFIG.get('azure_key_vault', 'key_vault_url'), azure_key_vault_key)


            # construct headers using key vault secrets
            authorization = '{0} {1}'.format('Bearer', secret_keys_dict['edxaccesstoken'])
            edx_headers = dict(Authorization=authorization, X_API_KEY=secret_keys_dict['edxapikey'])


            headers = {
                'Content-Type': 'application/json',
                'Ocp-Apim-Subscription-Key': secret_keys_dict['ldsubscriptionkey'],
                'Authorization': catalog_service.get_access_token_ld(
                    CONFIG.get('ld', 'ld_authorityhosturl'),
                    CONFIG.get('ld', 'ld_tenant'),
                    CONFIG.get('ld', 'ld_resource'),
                    secret_keys_dict['ldclientid'],
                    secret_keys_dict['ldclientsecret']
                    )
                }
            if integration_type == "course_consumption":
                catalog_service.get_and_post_consumption_data(
                    CONFIG.get('edx', 'edx_course_consumption_url'),
                    edx_headers,
                    headers,
                    CONFIG.get('ld', 'ld_consumption_url'),
                    CONFIG.get('ld', 'source_system_id'),
                    CONFIG.get('general', 'submitted_by'),
                    CONFIG.get('general', 'api_time_log_file'),
                    int(CONFIG.get('general', 'time_delta_retention'))
                    )
                log.info("End of the Catalog Integration process")

            elif integration_type == "course_catalog":
                catalog_data = catalog_service.get_course_catalog_data(
                    CONFIG.get('edx', 'edx_course_catalog_url'),
                    edx_headers
                    )
                catalog_service.post_data_ld(
                    CONFIG.get('ld', 'ld_catalog_url'),
                    headers,
                    catalog_service.catalog_data_mapping(CONFIG.get('ld', 'source_system_id'), catalog_data)
                    )
                log.info("End of the Course Catalog Integration process")
            break

        except Exception: # pylint: disable=W0703

            attempts += 1
            log.error("Exception occured while running the script", exc_info=True)

if __name__ == "__main__":
    VALID_ARGS = ['course_catalog', 'course_consumption']
    INPUT_ARGS = sys.argv[1]
    if INPUT_ARGS in VALID_ARGS:

        sync_edx_data(INPUT_ARGS)
    else:
        print('Invalid arguments passed. Choose from the following arguments.\n 1.course_catalog \n 2.course_consumption')
