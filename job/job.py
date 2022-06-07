'''
Run this job file from automation_tests/ folder using:=

easypy job/job.py -testbed_file etc/testbed.yaml -no_mail

'''

import os
import sys
from ats.easypy import run
import argparse

import logging
testbed_file = os.path.join(os.path.dirname(os.path.abspath(__file__))+'/../testbed', "testbed.yaml")
cdo_probe_payload_file = os.path.join(os.path.dirname(os.path.abspath(__file__))+'/../utility', "cdo_probe_payload.json")
aws_probe_payload_file = os.path.join(os.path.dirname(os.path.abspath(__file__))+'/../utility', "aws_probe_payload.json")

logging.basicConfig(filename='observability_elk.log',
                    level=logging.INFO,  #DEGUG
                    format='%(asctime)s %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p')

SCRIPT_DIR = os.path.dirname(os.path.dirname(__file__))

parser = argparse.ArgumentParser(description="extending easypy args")
parser.add_argument('--browser', help='Choose Browser from chrome, firefox or safari', nargs='?', default='chrome')
parser.add_argument('--set_headless', help='Set a Browser to run in headless mode', nargs='?', default='true')

def main():

    """
    aws_test_case = 'regression/case_aws.py'
    result = run(testscript=aws_test_case, testbed_file=testbed_file, aws_probe_payload_file=aws_probe_payload_file, beat='aws')
    if not result and result != 'passed':
         print("==============> setup Failed, Exiting <===============")
         print("Failure on Test case: ", aws_test_case)
         return
    """

    cdo_test_case = 'regression/case_cdo.py'
    result = run(testscript=cdo_test_case, testbed_file=testbed_file, cdo_probe_payload_file=cdo_probe_payload_file, beat='cdo')
    if not result and result != 'passed':
         print("==============> setup Failed, Exiting <===============")
         print("Failure on Test case: ", cdo_test_case)
         return


