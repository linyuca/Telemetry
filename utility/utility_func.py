import sys

import yaml
import requests
import logging
import os
import json
from datetime import date

requests.packages.urllib3.disable_warnings()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def get_msx_token(msx_beat_ip, msx_port, msx_client_user, msx_client_pass):
    try:
        # Get MSX TOKEN
        url = "http://{ip}:{port}/idm/v2/token".format(ip=msx_beat_ip, port=msx_port)
        logger.info("GET MSX Token: url {}".format(url))
        payload = 'grant_type=password&username=superuser&password=superuser'
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        response = requests.request("POST", url, auth=(msx_client_user, msx_client_pass), headers=headers, data=payload)
        if response.status_code == 200:
            json_response = response.content.decode('utf-8')
            if json_response:
                msx_json = json.loads(json_response)
                if "access_token" in msx_json:
                    msx_token = msx_json["access_token"]
                    return msx_token
    except Exception as e:
        logger.error("Exception occured:: ", e)
        sys.exit(1)


def read_json_file(jfname):
    with open(jfname, "rt", encoding='utf-8') as json_data:
        data = json.load(json_data)
        return data

def get_elasticsearch_version(ip, port, header):
    beat = "http://" + str(ip) + ":" + str(port)
    response= requests.get(beat, headers=header, verify=False)
    if response.status_code == 200:
        logging.info("Query success ..." + beat)
        r_json = response.json()
        return r_json
    else:
        logging.error("Query failed ..." + beat)
        return False

def get_elasticsearch_doc(beat, url, data, header):
    url = beat + url
    logging.info("url:"+url)
    response= requests.get(url, headers=header, data=data, verify=False)
    if response.status_code > 300:
        logging.error("GET failed ..."+url)
        return False
    logging.info("GET success ..."+url)
    r_json=response.json()

    return r_json

def get_elasticsearch_index(ip, port, beat):
    url = "http://" + str(ip) + ":" + str(port) + "/_cat/indices"
    today = date.today()
    today = today.strftime("%Y.%m.%d")
    try:
        res = requests.get(url)
        if res.status_code == 200:
            lines = res.content.decode('utf-8')
            for line in lines.split('\n'):
                lineList = line.split()
                if len(lineList) and lineList[0] in ['green', 'yellow']:
                    index = lineList[2].strip()
                    if index.startswith(beat) and index.endswith(today):
                        return index
            else:
                return False
        else:
            return False
    except Exception as e:
        logger.error("Exception occured:: ", e)
        sys.exit(1)


def get_latest_elasticsearch_timestamp(ip, port, index, header):
    beat = "http://" + str(ip) + ":" + str(port)
    url = "/" + index + "/_search"
    logger.info("*** url: {}".format(url))
    data = { "size": 2000 }
    timestamp = ''
    try:
        res = get_elasticsearch_doc(beat, url, json.dumps(data), header)
        if res:
            for i in res['hits']['hits']:
                if timestamp < i['_source']['@timestamp']:
                    timestamp = i['_source']['@timestamp']
            return timestamp
        else:
            return False
    except Exception as e:
        logger.error("Exception occured:: ", e)
        sys.exit(1)

