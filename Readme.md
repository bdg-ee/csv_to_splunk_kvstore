# Readme

---

**TABLE OF CONTENTS**
- [About](#about)
- [Setup](#setup)
- [Usage](#usage)
- [References](#references)

---

## About

This script builds out a Splunk KVStore from a csv file. 

More information about Splunk KVStore - how it differs from a simple lookup and when to use it, is explained thoroughly in Splunk's documentation.

## Setup

Setup is pretty simple
1. Use python >= 3.7, and install the moduless in `requirements.txt`.
2. Set desired values in the configuration file. The file must be in the `*.ini`. format that can be read by python's `configparser`. By default the script reads from `splunk_kvstore.ini`.
3. The input file to create the kvstore from (specified in the configuration file) must be a valid `*.csv` file and located in same directory as the script


**Other Requirements**:
- Splunk user account with administrator privileges
- The splunk server, and your system, need to be configured to allow interaction with the REST API over port 8089. The REST API can be interacted with and tested using `curl` and making sure you can pull and push data. Below is an example command to pull a list of apps using the Splunk REST API.
  ```
  curl -k -u username:pass https://<SPLUNK_SERVER>:8089/services/apps/local
  ```

## Usage

Run the script with
```
python3 csv2kvstore.py
```

**WARNING**: This script will make minor configuration changes to Splunk if needed to match settings in the configuration file.

#### Functionality
If it doesn't already exist, the script will use the REST API to create a collection on the splunk server. Collections are normally defined in `collections.conf` at the location `$SPLUNK_HOME/etc/apps/SPLUNK_APP_WITH_COLLECTION/local/collections.conf`.

The script will then define a stanza in `limits.conf` and set the `max_documents_per_batch_save ` value. The splunk application `limits.conf` is modified under, and the value set, are configured in the configuration file.

Finally, the script reads through the csv and pushes it in chunks to the splunk server using the REST API, building out the KVStore.

#### Logging
The script will write to the log file specified in the configuration (default is `csv2splunk.log`).

#### User output
To get verbose output to stdout, set `DEBUG_MODE = 1` in the configuration file. Otherwise, the log file will contain all logging.

#### Viewing the kvstore in Splunk

To use the KV store, a lookup needs to be defined using it. This can be done through the Web UI, or with an entry like the below in  `transforms.conf`:
  ```
  [LOOKUP_NAME]
  external_type = kvstore
  collection = COLLECTION_NAME
  fields_list = <LIST_OF_FIELD_NAMES>
  ```
To view the kvstore-based lookup, type the following into the Splunk searchbar:
  ```
  | inputlookup LOOKUP_NAME
  ```

## References:
- [Splunklib](https://github.com/splunk/splunk-sdk-python/blob/master/examples/kvstore.py)
