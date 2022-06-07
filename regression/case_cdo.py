from ats import aetest
import time
import os
import sys
import logging
import json
file_path = os.path.split(os.path.dirname(__file__))[0]
sys.path.append(file_path)
from datetime import date, datetime, timedelta

import warnings

from utility.utility_func import *
from pyats import aetest
from pyats.topology import loader

warnings.filterwarnings("ignore")

file_path = os.path.split(os.path.dirname(__file__))[0]
sys.path.append(file_path)
from utility.utility_func import *

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

currentFuncName = lambda n=0: sys._getframe(n + 1).f_code.co_name
index = False
device_id = False
customer_id = False

class CommonSetup(aetest.CommonSetup):

    @aetest.subsection
    def initialize_connect(self, testbed_file, cdo_probe_payload_file, beat='cdo'):
        logger.info(".................. Common set up -> Testbed bring up ................. ")

        global TB, msx_cdo_beat_ip, msx_port, cdo_beat_port, msx_cdo_client_user, msx_cdo_client_pass, probe_payload_file, ELK_VERSION, HEADER, CDO_TOKEN, URL_SFCN_DEVICES, URL_ASAC_DEVICES, URL_DNG_USERS, URL_RAVPN_USERS, elastic_search_ip, elastic_search_port

        # Create the testbed file
        testbed = loader.load(testbed_file)
        logger.info(testbed_file)
        TB = testbed
        probe_payload_file = cdo_probe_payload_file
        msx_cdo_beat_ip = TB.custom['msx-cdo-beat-ip']
        msx_port = TB.custom['msx-port']
        cdo_beat_port = TB.custom['cdo-beat-port']
        msx_cdo_client_user = TB.custom['msx-cdo-client-user']
        msx_cdo_client_pass = TB.custom['msx-cdo-client-pass']
        ELK_VERSION = TB.custom['ELK-VERSION']
        HEADER = TB.custom['HEADER']
        CDO_TOKEN = TB.custom['CDO-TOKEN']
        URL_SFCN_DEVICES = TB.custom['URL-SFCN-DEVICES']
        URL_ASAC_DEVICES = TB.custom['URL-ASAC-DEVICES']
        URL_DNG_USERS= TB.custom['URL-DNG-USERS']
        URL_RAVPN_USERS= TB.custom['URL-RAVPN-USERS']

        logger.info("*** {}".format(currentFuncName()))
        elasticsearch = TB.devices[beat]
        elastic_search_ip = TB.custom['elastic-search-ip']
        elastic_search_port = TB.custom['elastic-search-port']
        self.parent.parameters['elasticsearch'] = elasticsearch

class Test_cdo_beat(aetest.Testcase):

    def trigger_cdo_beat(self):
        global msx_token, customer_id
        try:
            msx_token = get_msx_token(msx_cdo_beat_ip, msx_port, msx_cdo_client_user, msx_cdo_client_pass)
            msx_token = "Bearer " +msx_token
            url = "http://{ip}:{port}/config/host".format(ip=msx_cdo_beat_ip,port=cdo_beat_port)
            headers = {'Authorization': msx_token, 'Content-Type': 'application/json'}
            payload = read_json_file(probe_payload_file)
            customer_id = payload['customerId']
            logger.info("*** {} customer_id: {}".format(currentFuncName(), url, customer_id))
            logger.info("Trigger CDO BEAT")
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
        ElasticSearch running and health
        Collecte Devices and Users number
        """
        timestamp = get_latest_elasticsearch_timestamp(elastic_search_ip, elastic_search_port, index, HEADER)
        if timestamp == False:
            sys.exit(1)

        logger.info("*** {} latest timestamp: {}".format(currentFuncName(), timestamp))
        try:
            logger.info("*** {}".format(currentFuncName()))

            beat = "http://" + str(elastic_search_ip) + ":" + str(elastic_search_port)
            url = "/" + index + "/_search"
            #data =  { "query": { "match": { "@timestamp": timestamp }}}

            data = {"query": {"range": { "@timestamp" :{ "gte": timestamp}}}}
            time.sleep(10)

            #wait the ElasticSearch receives a few data from CDO Beat
            total_retry = 1
            while True:
                res = get_elasticsearch_doc(beat, url, json.dumps(data), HEADER)
                list_data = res['hits']['hits']

                logger.info("*** Retry {} to get all data after timestamp {} ".format(total_retry, timestamp))
                if len(list_data) >2:
                    logger.info("*** Get {} data after timestamp {} ".format(len(list_data), timestamp))
                    break
                else:
                    time.sleep(5)
                    total_retry += 1
                    if total_retry > 20:
                        break

            for i in list_data:
                print(customer_id, i['_source']['customerId'])
                if customer_id == i['_source']['customerId']:
                    source = i['_source']
                    break
            else:
                logger.error("*** {}: not find the customer ID".format(currentFuncName()))
                sys.exit(1)

            self.customerId = source['customerId']
            self.deviceId = source['deviceId']
            logger.info("*** {} customerId: {}".format(currentFuncName(), source['customerId']))

            devices = source['cdoDevices']
            num_SFCN_Devs = 0
            num_ASAC_Devs = 0
            for dev in devices:
                if dev['deviceType'] == 'SFCN_DNG':
                    num_SFCN_Devs += 1
                elif dev['deviceType'] == 'ASAC':
                    num_ASAC_Devs += 1
            logger.info("*** {} Total Devices: {}".format(currentFuncName(), len(devices)))
            logger.info("*** {} SFCN_DNG: {}".format(currentFuncName(), num_SFCN_Devs))
            logger.info("*** {} ASAC_DNG: {}".format(currentFuncName(), num_ASAC_Devs))

            dngUsersList = source.get('dngUsers', [])
            logger.info("*** {} DNG Users: {}".format(currentFuncName(), len(dngUsersList)))

            raVpnUsersList = source.get('raVpnUsers', [])
            logger.info("*** {} RA-VPN Users: {}".format(currentFuncName(), len(raVpnUsersList)))

            self.num_SFCN_Devs = num_SFCN_Devs
            self.num_ASAC_Devs = num_ASAC_Devs
            self.num_dngUsers = len(dngUsersList)
            self.num_raVpnUsers = len(raVpnUsersList)
        except Exception as e:
            logger.error("Exception occured:: ", e)
            sys.exit(1)

    def get_sfcn_dng_device_from_cdo(self):
        try:
            # Get device_name, connectivity state, config state for SFCN DNG devices
            url = URL_SFCN_DEVICES
            headers = {'Authorization': CDO_TOKEN}
            headers.update(HEADER)
            response = requests.request("GET", url, headers=headers, data=None)

            sfcn_dng_device_list = []
            if response.status_code == 200:
                json_response = response.content.decode('utf-8')
                if json_response:
                    device_json = json.loads(json_response)
                    for each_response in device_json:
                        dict = {}
                        dict["device_name"] = each_response["name"]
                        dict["connectivityState"] = each_response["connectivityState"]
                        dict["configState"] = each_response["configState"]
                        sfcn_dng_device_list.append(dict)
                    #logger.info("*** {} SFCN DGN DEVICE LIST: {}".format(currentFuncName(), sfcn_dng_device_list))
                    return len(sfcn_dng_device_list)
            return False
        except Exception as e:
            logger.error("Exception occured:: ", e)
            sys.exit(1)

    def get_sfcn_asac_device_from_cdo(self):
        try:
            # Get device_name, connectivity state, config state for SFCN ASAC devices
            url = URL_ASAC_DEVICES
            headers = {'Authorization': CDO_TOKEN}
            headers.update(HEADER)
            response = requests.request("GET", url, headers=headers, data=None)
            sfcn_device_list = []
            if response.status_code == 200:
                json_response = response.content.decode('utf-8')
                if json_response:
                    device_json = json.loads(json_response)
                    # print(device_json)
                    for each_response in device_json:
                        dict = {}
                        dict["device_name"] = each_response["name"]
                        dict["connectivityState"] = each_response["connectivityState"]
                        dict["configState"] = each_response["configState"]
                        sfcn_device_list.append(dict)
                    #logger.info("*** {} SFCN ASAC DEVICE LIST: {}".format(currentFuncName(), sfcn_device_list))
                    return len(sfcn_device_list)
            return False
        except Exception as e:
            logger.error("Exception occured:: ", e)
            sys.exit(1)

    def get_dng_users_from_cdo(self):
        try:
            limit = 200
            offset = 0
            # Get current time in local timezone
            current_time = datetime.now()
            current_timestamp = str(datetime.timestamp(current_time))
            ts = current_timestamp.split('.',1)
            final_timestamp = ts[0]
            timestamp = "timestamp%3A%5B*+TO+" + final_timestamp + "%5D"
            url = URL_DNG_USERS.format(timestamp=timestamp,limit=limit, offset=offset)
            headers = {'Authorization': CDO_TOKEN}
            headers.update(HEADER)
            response = requests.request("GET", url, headers=headers, data=None)
            user_list = []
            if response.status_code == 200:
                json_response = response.content.decode('utf-8')
                if json_response:
                    dng_user_json = json.loads(json_response)
                    mfa_events = dng_user_json["mfaEvents"]
                    for each_user in mfa_events:
                        user_dict={}
                        user_dict["deviceName"] = each_user["deviceName"]
                        user_dict["username"] = each_user["username"]
                        user_list.append(user_dict)
                    # logger.info("*** {} DNG USERS LIST: {}".format(currentFuncName(), user_list))
                    return len(user_list)
            return False
        except Exception as e:
            logger.error("Exception occured:: ", e)
            sys.exit(1)

    def get_ravpn_users_from_cdo(self):
        try:
            limit = 50
            offset = 0
            # Get current time in local timezone
            current_time = datetime.now()
            current_timestamp = str(datetime.timestamp(current_time))
            ts = current_timestamp.split('.',1)
            final_timestamp = ts[0]
            timestamp = "loginTime%3A%5B*+TO+" + final_timestamp + "%5D"
            url = URL_RAVPN_USERS.format(limit=limit,offset=offset, timestamp=timestamp)
            headers = {'Authorization': CDO_TOKEN}
            headers.update(HEADER)
            response = requests.request("GET", url, headers=headers, data=None)
            user_list = []
            if response.status_code == 200:
                json_response = response.content.decode('utf-8')
                if json_response:
                    ravpn_user_json = json.loads(json_response)
                    sessions = ravpn_user_json["sessions"]
                    for each_user in sessions:
                        user_dict={}
                        user_dict["deviceName"] = each_user["deviceName"]
                        user_dict["username"] = each_user["username"]
                        user_list.append(user_dict)
                    logger.info("*** {} RA-VPN Users LIST: {}".format(currentFuncName(), user_list))
                    return len(user_list)
            return False
        except Exception as e:
            logger.error("Exception occured:: ", e)
            sys.exit(1)

    @aetest.setup
    def setup(self):
        logger.info("Test Case set up")

    @aetest.test
    def test_1_trigger_cdo_beat(self):
        # Trigger cdo beat to collect data from CDO and store it to ElasticSearch
        logger.info("Trigger cdo beat to collect data from CDO and store it to ElasticSearch")
        if self.trigger_cdo_beat() == True:
            logger.info("*** {} trigger CDO Beat success!".format(currentFuncName()))
        else:
            logger.error("*** {} trigger CDO Beat failed!".format(currentFuncName()))
            sys.exit(1)
        assert customer_id != False

    @aetest.test
    def test_2_elasticsearch_version(self, beat='cdo'):
        """
        ElasticSearch is running and it's version is correct
        """
        # time.sleep(120)
        logger.info("*** {}".format(currentFuncName()))
        res = get_elasticsearch_version(elastic_search_ip, elastic_search_port, HEADER)
        if res == False:
            logger.error("{}: {}".format(currentFuncName(), "requests get failed ..."))
            sys.exit(1)
        else:
            assert res['version']['number'] == ELK_VERSION

    @aetest.test
    def test_3_elasticsearch_document_and_search(self):
        # get today's index
        global index
        index = get_elasticsearch_index(elastic_search_ip, elastic_search_port, 'cdobeat')
        logger.info("*** {} index: {}!".format(currentFuncName(), index))
        if index == False:
            logger.error("*** {} Get index failed!".format(currentFuncName()))
            sys.exit(1)
        assert index != False

        # query ElasticSearch to get number of device and users
        # only call once collection data
        self.query_elasticsearch_indices()
        print(customer_id)
        print(self.customerId)
        assert customer_id == self.customerId

    @aetest.test
    def test_4_num_sfcn_dng_device(self):
        logger.info("*** {} elasticsearch num SFCN Devs: {}".format(currentFuncName(), self.num_SFCN_Devs))
        cdo_SFCN_device_number = self.get_sfcn_dng_device_from_cdo()
        logger.info("*** {} CDO SFCN Device number: {}".format(currentFuncName(), cdo_SFCN_device_number))
        assert self.num_SFCN_Devs == cdo_SFCN_device_number

    @aetest.test
    def test_5_num_sfcn_asac_device(self):
        logger.info("*** {} elasticsearch num ASAC Devs: {}".format(currentFuncName(), self.num_ASAC_Devs))
        cdo_ASAC_device_number = self.get_sfcn_asac_device_from_cdo()
        logger.info("*** {} CDO ASAC Device number: {}".format(currentFuncName(), cdo_ASAC_device_number))
        assert self.num_ASAC_Devs == cdo_ASAC_device_number

    @aetest.test
    def test_6_num_dng_user(self):
        logger.info("*** {} num DNG Users: {}".format(currentFuncName(), self.num_dngUsers))
        cdo_num_dng_user = self.get_dng_users_from_cdo()
        logger.info("*** {} DNG Users number: {}".format(currentFuncName(), cdo_num_dng_user))
        assert self.num_dngUsers == cdo_num_dng_user

    @aetest.test
    def test_7_num_ravpn_user(self):
        logger.info("*** {} num RA-VPN Users: {}".format(currentFuncName(), self.num_raVpnUsers))
        cdo_num_ravpn_users = self.get_ravpn_users_from_cdo()
        logger.info("*** {} RA-VPN Users number: {}".format(currentFuncName(), cdo_num_ravpn_users))
        assert self.num_raVpnUsers == cdo_num_ravpn_users

class CommonCleanup(aetest.CommonCleanup):

    @aetest.subsection
    def cleanup_if_need(self):
        logger.info("** {}".format(currentFuncName()))


