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
    # todo make this not overwrite existing values
    file = open('config.yml', 'w')
    yaml.dump({'token': 'your mom',
               'message-id': 1119465976149327892,
               'url': 'https://example.com',
               'guild-id': 1112913686626054184,
               'member-role-id': 1132112701661921351,
               'pass-role-id': 1132727677317562436,
               'fail-role-id': 1132727585466503228,
               'challenge-channel-id': 1119465092262666271},
              file)
    file.close()
