#!/usr/bin/python3
"""
Last Updated: 04 APR 2021

See Readme.md
"""

__author__ = "bdg-ee"

import csv, sys, os, json, datetime
import time
import configparser

# Load 3rd party modules
try:
    import splunklib
    import splunklib.client as spl_client
    import requests
    import urllib
    import http.client
    import ssl
    from xml.etree import ElementTree
except Exception as e:
    print("Required Python Packags can't be loaded!")
    sys.exit(2)

# GLOBAL FIELDS
_CONFIG_FILE = "csv2kvstore.ini"
_UPDATE_INTERVAL = 20 # How often to update user during processing, in seconds
_MAX_DOCUMENTS_PER_BATCH_SAVE = "1700" # Must be an integer string

# READ CONFIG
config = configparser.ConfigParser()
config.read(_CONFIG_FILE)
_DEBUGMODE = config['SPLUNK']['DEBUG_MODE']
_LOG_FILE = config['SPLUNK']['LOG_FILE']
input_file = config['SPLUNK']['INPUT_CSV']
splunk_server = config['SPLUNK']['SPLUNK_SERVER']
splunk_server_port = config['SPLUNK']['SPLUNK_SERVER_PORT']
splunk_app = config['SPLUNK']['SPLUNK_APP']
collection_owner = config['SPLUNK']['COLLECTION_OWNER']
collection_name = config['SPLUNK']['COLLECTION_NAME']
splunk_user = config['SPLUNK']['SPLUNK_USER']
refresh = config['SPLUNK'].getboolean('DELETE_AND_REBUILD')
_RELOAD_URL = f"https://{splunk_server}:8000en-US/debug/refresh?entity=apps/local/{splunk_app}"

def log(msg):
    """Logs to file"""
    with open(os.path.join(_LOG_FILE), "a") as f:
        f.write(f"\n{str(datetime.datetime.now().isoformat())},{msg}")
        if _DEBUGMODE == True:
            print(msg)


def get_fieldnames(filename):
    """Simply grabs fieldnames of csv"""
    data = []
    fieldnames = []
    with open(filename,"r") as csvfile:
        csvReader = csv.DictReader(csvfile)
        fieldnames = csvReader.fieldnames

    return fieldnames


def reload_splunk(pw):
    """Do the equivalent of a debug/refresh on splunk, need valid session token"""
    try:
        r = requests.post(_RELOAD_URL, auth=(splunk_user, pw),verify=False)

        if r.status_code == requests.codes.ok:
            log(f"script_action=success,msg=reloaded {splunk_server}.")
        else:
            log(f"script_action=failed,msg=failed reload of {splunk_server}, but no exceptions thrown.")
    except Exception as e:
        log(f"script_action=failed,msg=failed reload of {splunk_server}. {e}")


def read_and_postDataToSplunk(filename, collection):
    """Opens CSV and starts reading and pushing data to splunk"""

    total_records = 0
    try:
        start_time = time.time()
        last_time = start_time
        with open(filename,"r") as csvfile:
            csvReader = csv.DictReader(csvfile)
            log(f"script_action=info,msg=input csv file {filename} opened successfully.")
            cnt = 0
            items = []
            for row in csvReader:
                # Add record to list of dicts
                items.append(row)
                cnt += 1

                #
                if cnt >= int(_MAX_DOCUMENTS_PER_BATCH_SAVE):
                    collection.data.batch_save(*items)
                    total_records += cnt
                    
                    # Reset count and clear temp list of data
                    cnt=0
                    items.clear()

                    # Check if we need to give a user update
                    if time.time()-last_time > _UPDATE_INTERVAL:
                        passed_time = time.time()-start_time
                        log(f"script_action=processing,msg=at {passed_time:.1f} secs, {total_records} records pushed to kvstore {collection_name} on splunk server {splunk_server}.")
                        last_time = time.time()

            # Send last set
            if len(items) > 0:
                collection.data.batch_save(*items)
                total_records += cnt
                cnt=0

        log(f"script_action=success,msg=pushed {total_records} records to kvstore {collection_name} on splunk server {splunk_server} in {time.time()-start_time:.1f} seconds.")

    except Exception as e:
        log(f"script_action=failed,msg=could not push data to splunk server {splunk_server}. Error occurred with {total_records} pushed. {e}")

def removeDataFromSplunk(data):
    # TODO
    pass

if __name__ == "__main__":
    
    pw = input(f"Please enter password for user {splunk_user} and press <Enter>: ")

    # Set timeout via connection handler
    connectionHandler = splunklib.binding.handler(timeout = 3)
    
    # Try to connect
    try:
        s=spl_client.connect(host=splunk_server,port=splunk_server_port,
            username=splunk_user,password=pw,app=splunk_app, owner=collection_owner,
            handler=connectionHandler)
        if refresh:
            log(f"script_action=warning,msg=deleting the kvstore {collection_name} from {splunk_server} because DELETE_AND_REBUILD is set to True.")
            s.kvstore.delete(collection_name)
    
    except Exception as e:
        log(f"script_action=error,msg=could not connect to splunk server {splunk_server}. {e}")
        sys.exit(2)

    # Check collection exists, and setting is correct for stanza in collections.conf
    # create/update collection as needed
    avail_collections = [collection.name for collection in s.kvstore]
    if collection_name not in avail_collections:
        log(f"script_action=warning,msg=could not find collection {collection_name} on server {splunk_server} - trying to create...")
        s.kvstore.create(collection_name)
        log(f"script_action=success,msg=created collection {collection_name} on server {splunk_server}.")
    else:
        log(f"script_action=info,msg=verified collection {collection_name} on server {splunk_server}.")

    # Check setting in limits.conf is correct for max_documents_per_batch_save
    try:
        conf = s.confs["limits"]
        # Create stanza if needed
        if "kvstore" not in [s.name for s in conf]:
            conf.create("kvstore")
            # Reload the searchhead for this to take effect
            reload_splunk(pw)
            # Refresh the configuration
            conf.refresh()
            log(f"script_action=success,msg=created kvstore stanza in limits.conf.")
            
        # Confirm ky:value entry under stanza is accurate
        stanza = s.confs["limits"]["kvstore"]
        stanza_key_exists = False
        reload_needed = False
        for key, value in splunklib.six.iteritems(stanza.content):
            if key == "max_documents_per_batch_save" and value!=_MAX_DOCUMENTS_PER_BATCH_SAVE:
                stanza.submit({"max_documents_per_batch_save":_MAX_DOCUMENTS_PER_BATCH_SAVE})
                stanza_key_exists = True
                reload_needed = True
                log(f"script_action=success,msg=set max_documents_per_batch_save to {_MAX_DOCUMENTS_PER_BATCH_SAVE}.")
        if not stanza_key_exists:
            stanza.submit({"max_documents_per_batch_save":_MAX_DOCUMENTS_PER_BATCH_SAVE})
        if reload_needed: reload_splunk(pw)
        log(f"script_action=info,msg=verified limits.conf max_documents_per_batch_save value is {_MAX_DOCUMENTS_PER_BATCH_SAVE}.")
    except Exception as e:
        log(f"script_action=failed,msg=failed setting limits.conf max_documents_per_batch_save value to {_MAX_DOCUMENTS_PER_BATCH_SAVE}. {e}")
 
    log(f"script_action=processing,file={input_file},msg=pushing to splunk")
    read_and_postDataToSplunk(input_file, s.kvstore[collection_name])

# EOF