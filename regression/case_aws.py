from ats import aetest
import time
import os
import sys
import logging
import json
import warnings
from pyats.topology import loader

warnings.filterwarnings("ignore")

file_path = os.path.split(os.path.dirname(__file__))[0]
sys.path.append(file_path)
from utility.utility_func import *

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

currentFuncName = lambda n=0: sys._getframe(n + 1).f_code.co_name
es_tenant_Id = None
tenant_id = None
index = None
NUM_HITS = 4   #collect this many hits and check if the tenant_id is in the list

class CommonSetup(aetest.CommonSetup):

    @aetest.subsection
    def initialize_connect(self, testbed_file, aws_probe_payload_file, beat='aws'):
        logger.info(".................. Common set up -> Testbed bring up ................. ")
        global TB, msx_port, msx_aws_beat_ip, aws_swagger_ip,  aws_beat_port, msx_aws_client_user, msx_aws_client_pass, probe_payload_file, ELK_VERSION, HEADER, elastic_search_ip, elastic_search_port
        # Create the testbed file
        testbed = loader.load(testbed_file)
        logger.info(testbed_file)
        TB = testbed
        probe_payload_file = aws_probe_payload_file
        msx_aws_beat_ip = TB.custom['msx-aws-beat-ip']
        msx_port = TB.custom['msx-port']
        aws_swagger_ip = TB.custom['aws-swagger-ip']
        aws_beat_port = TB.custom['aws-beat-port']
        msx_aws_client_user = TB.custom['msx-aws-client-user']
        msx_aws_client_pass = TB.custom['msx-aws-client-pass']
        ELK_VERSION = TB.custom['ELK-VERSION']
        logger.info("*** {}".format(currentFuncName()))
        HEADER = TB.custom['HEADER']
        elastic_search_ip = TB.custom['elastic-search-aws-ip']
        elastic_search_port = TB.custom['elastic-search-aws-port']

class Test_aws_beat(aetest.Testcase):


    def trigger_aws_beat(self):
        global msx_token, tenant_id
        try:
            msx_token = get_msx_token(msx_aws_beat_ip,msx_port, msx_aws_client_user, msx_aws_client_pass)
            msx_token = "Bearer " +msx_token
            url = "http://{ip}:{port}/config/host".format(ip=aws_swagger_ip,port=aws_beat_port)
            headers = {'Authorization': msx_token, 'Content-Type': 'application/json'}
            payload = read_json_file(probe_payload_file)
            tenant_id = payload['metrics']['aws']['tenantId']
            logger.info("*** {} url: {} and tenant_id: {}".format(currentFuncName(), url, tenant_id))
            logger.info("Trigger AWS BEAT")
            response = requests.request("POST", url, headers=headers, data=json.dumps(payload))
            if response.status_code == 200:
                return True
            else:
                return False
        except Exception as e:
            logger.error("Exception occured:: ", e)
            sys.exit(1)


    def query_elasticsearch_indices(self):
        """
        ElasticSearch is running and it's version is correct
        """
        #index = "awsbeat-4.3.0-snapshot-2022.05.31"
        #timestamp = "2022-05-26T05:08:24.487Z"

        timestamp = get_latest_elasticsearch_timestamp(elastic_search_ip, elastic_search_port, index, HEADER)
        if timestamp == False:
            sys.exit(1)
        logger.info("*** {} latest timestamp: {}".format(currentFuncName(), timestamp))

        try:
            logger.info("*** {}".format(currentFuncName()))


            beat = "http://" + str(elastic_search_ip) + ":" + str(elastic_search_port)
            url = "/" + index + "/_search"
            #wait the ElasticSearch receives a few data from CDO Beat
            data = {"query": {"range": { "@timestamp" :{ "gte": timestamp}}}}
            time.sleep(10)
            total_retry = 1
            while True:
                res = get_elasticsearch_doc(beat, url, json.dumps(data), HEADER)
                list_data = res['hits']['hits']

                logger.info("*** Retry {} to get all data after timestamp {} ".format(total_retry, timestamp))
                if len(list_data) >NUM_HITS:
                    logger.info("*** Get {} data after timestamp {} ".format(len(list_data), timestamp))
                    break
                else:
                    time.sleep(5)
                    total_retry += 1
                    if total_retry > 20:
                        logger.error("*** {}: not find the tenant ID".format(currentFuncName()))
                        raise "Errlr: tenantId not find..."

            for i in list_data:
                # print(tenant_id, i['_source']['tenantId'])
                if tenant_id == i['_source']['tenantId']:
                    source = i['_source']
                    break
            else:
                logger.error("*** {}: not find the tenant ID".format(currentFuncName()))
                sys.exit(1)

            bytesIn = source['bytesIn']
            bytesOut = source['bytesOut']
            operStatus = source['operationalStatus']
            tenantId = source['tenantId']
            bytesOutToDestination = source['bytesOutToDestination']
        except Exception as e:
            logger.error("Exception occured:: ", e)
            sys.exit(1)

        return bytesIn, bytesOut, tenantId, operStatus, bytesOutToDestination 


    @aetest.setup
    def setup(self):
        logger.info("*** {}".format(currentFuncName()))

    @aetest.test
    def test_1_trigger_aws_beat(self):
        # Trigger aws beat to collect data from transit gateway and store it to ElasticSearch
        logger.info("Trigger aws beat to collect data from transit gateway and store it to ElasticSearch")
        if self.trigger_aws_beat() == True:
            logger.info("*** {} trigger AWS Beat success! tenantId: {}".format(currentFuncName(), tenant_id))
        else:
            logger.error("*** {} trigger AWS Beat failed!".format(currentFuncName()))
            sys.exit(1)

        assert tenant_id  != None

    @aetest.test
    def test_2_elasticsearch_version(self, beat='aws'):
        logger.info("*** {}".format(currentFuncName()))
        res = get_elasticsearch_version(elastic_search_ip, elastic_search_port, HEADER)
        if res == False:
            logger.error("{}: {}".format(currentFuncName(), "requests get failed ..."))
            sys.exit(1)
        else:
            assert res['version']['number'] == ELK_VERSION

    @aetest.test
    def test_3_elasticsearch_document_and_search(self):
        logger.info("*** {}".format(currentFuncName()))
        global index
        index = get_elasticsearch_index(elastic_search_ip, elastic_search_port, 'awsbeat')
        logger.info("*** {} index: {}!".format(currentFuncName(), index))
        if index == False:
            logger.error("*** {} Get index failed!".format(currentFuncName()))
            sys.exit(1)
        assert index != None

        # query ElasticSearch to get number bytesIn, bytesOut, tenantId
        # only call once collection data

        bytesIn, bytesOut, tenantId, operStatus, bytesOutToDestination = self.query_elasticsearch_indices()
        logger.info("*********** ELASTIC SEARCH OUTPUT **********************************")
        logger.info("**** TENANT ID: {} ".format(tenantId))
        logger.info("**** BYTES IN: {}".format(bytesIn))
        logger.info("**** BYTES OUT: {}".format(bytesOut))
        logger.info("**** OPERATIONAL STATUS: {} ".format(operStatus))
        logger.info("**** BYTES OUT TO DESTINATION: {} ".format(bytesOutToDestination))
        logger.info("*********************************************")
        assert 1 == 1


class CommonCleanup(aetest.CommonCleanup):

    @aetest.subsection
    def clean_if_need(self):
        logger.info("*** {}".format(currentFuncName()))
