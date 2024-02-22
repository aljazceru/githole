#!/bin/bash

# this is an ugly hack for demo purposes

# Path to the JSON files
ACL_FILE="git-daemon-export-ok"

# save $1 to file 
echo "$1" > /tmp/tmp_event.json

EVENT_FILE="/tmp/tmp_event.json"

# Check if jq is installed
if ! command -v jq &> /dev/null
then
    echo "jq could not be found. Please install jq to run this script."
    exit 1
fi

# Extract npub keys from the ACL dictionary in the ACL_FILE
acl_keys=$(jq '.ACL | keys[]' $ACL_FILE | sed 's/"//g') 

# write keys to file

echo "$acl_keys" > keys.txt
hex_keys=$(echo "$acl_keys"  | nak decode | jq .pubkey | sed 's/"//g')

echo "$hex_keys" > hex_keys.txt

# Extract the pubkey from the EVENT_FILE

pubkey=$(cat "$EVENT_FILE" | jq -r '.pubkey')
#echo $pubkey
#pubkey=$(jq -r '.pubkey' $EVENT_FILE)


# Check if the extracted pubkey is in the list of ACL keys
if echo "$hex_keys" | grep -q "$pubkey"; then
    echo "PASS"
else
    echo "FAIL"
fi

echo "pubkey: $pubkey" > /tmp/auth.log
echo "acl_keys: $acl_keys" >> /tmp/auth.log
echo "hex_keys: $hex_keys" >> /tmp/auth.log


#     "npub1aljazgxlpnpfp7n5sunlk3dvfp72456x6nezjw4sd850q879rxqsthg9jp": "admin"
