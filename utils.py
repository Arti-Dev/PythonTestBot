import dateutil.parser as parser


def hypixel_date_to_timestamp(date):
    time = parser.parse(date)
    return int(time.timestamp())
