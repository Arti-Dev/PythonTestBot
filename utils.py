import dateutil.parser as parser
import os
import yaml


def hypixel_date_to_timestamp(date):
    time = parser.parse(date)
    return int(time.timestamp())


def save_new_guid(new_guid):
    best_guid_file = open('bestguid.txt', 'w')
    best_guid_file.write(str(new_guid))
    best_guid_file.close()


def save_default_config():
    file = open('config.yml', 'w')
    yaml.dump({'token': 'your mom',
               'message-id': 1119465976149327892,
               'url': 'https://example.com'}, file)
    file.close()
