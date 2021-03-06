import datetime
import requests
import json
import re
import six
from django.conf import settings
from registrations.models import Source
from datetime import timedelta
from seed_services_client import (
    IdentityStoreApiClient,
    MessageSenderApiClient,
    StageBasedMessagingApiClient,
)

session = requests.Session()
http = requests.adapters.HTTPAdapter(max_retries=5)
https = requests.adapters.HTTPAdapter(max_retries=5)
session.mount('http://', http)
session.mount('https://', https)

identity_store_client = IdentityStoreApiClient(
    api_url=settings.IDENTITY_STORE_URL,
    auth_token=settings.IDENTITY_STORE_TOKEN,
    retries=5,
)

stage_based_messaging_client = StageBasedMessagingApiClient(
    api_url=settings.STAGE_BASED_MESSAGING_URL,
    auth_token=settings.STAGE_BASED_MESSAGING_TOKEN,
    retries=5,
)

message_sender_client = MessageSenderApiClient(
    api_url=settings.MESSAGE_SENDER_URL,
    auth_token=settings.MESSAGE_SENDER_TOKEN,
    retries=5,
)


def get_today():
    return datetime.datetime.today()


def calc_pregnancy_week_lmp(today, lmp):
    """ Calculate how far along the mother's prenancy is in weeks.
    """
    last_period_date = datetime.datetime.strptime(lmp, "%Y%m%d")
    time_diff = today - last_period_date
    preg_weeks = int(time_diff.days / 7)
    # You can't be one week pregnant (smaller numbers will be rejected)
    if preg_weeks == 1:
        preg_weeks = 2
    return preg_weeks


def calc_date_from_pregnancy_week(today, weeks):
    days = int(weeks) * 7
    last_period_date = today - timedelta(days=days)
    return last_period_date


def calc_baby_age(today, baby_dob):
    """ Calculate the baby's age in weeks.
    """
    baby_dob_date = datetime.datetime.strptime(baby_dob, "%Y%m%d")
    time_diff = today - baby_dob_date
    if time_diff.days >= 0:
        age_weeks = int(time_diff.days / 7)
        return age_weeks
    else:
        # Return -1 if the date is in the future
        return -1


def calc_baby_dob(today, weeks):
    days = int(weeks) * 7
    baby_dob = today - timedelta(days=days)
    return baby_dob


def normalize_msisdn(raw, country_code):

    if len(raw) <= 5:
        return raw

    raw = re.sub('[^0-9+]', '', raw)

    if raw[:2] == '00':
        return '+' + raw[2:]

    if raw[:1] == '0':
        return '+' + country_code + raw[1:]

    if raw[:1] == '+':
        return raw

    if raw[:len(country_code)] == country_code:
        return '+' + raw

    return raw


def get_identity(identity):
    return identity_store_client.get_identity(identity)


def get_identity_address(identity):
    return identity_store_client.get_identity_address(identity)


def get_address_from_identity(identity):
    last_address = None
    for address, detail in identity['details'].get(
            'addresses', {}).get('msisdn', {}).items():
        if detail.get('optedout', False) is True:
            pass
        if detail.get('default', False) is True:
            return address
        last_address = address
    return last_address


def search_identities(search_key, search_value):
    """
    Returns the identities matching the given parameters
    FIXME: This should be handled by identity_store_client when
    it supports pagination
    """
    url = "%s/%s/search/" % (settings.IDENTITY_STORE_URL, "identities")
    params = {search_key: search_value}
    headers = {
        'Authorization': 'Token %s' % settings.IDENTITY_STORE_TOKEN,
        'Content-Type': 'application/json'
    }
    r = session.get(url, params=params, headers=headers)
    r.raise_for_status()
    r = r.json()

    while True:
        for identity in r.get('results', []):
            yield identity
        if r.get('next'):
            r = session.get(r['next'], headers=headers)
            r.raise_for_status()
            r = r.json()
        else:
            break


def patch_identity(identity, data):
    """ Patches the given identity with the data provided
    """
    return identity_store_client.update_identity(identity, data=data)


def create_identity(data):
    """ Creates the identity with the data provided
    """
    return identity_store_client.create_identity(data)


def search_optouts(params=None):
    """
    Returns the optouts matching the given parameters
    FIXME: This should be handled by identity_store_client when
    it supports pagination
    """
    url = "%s/%s/search/" % (settings.IDENTITY_STORE_URL, "optouts")
    headers = {
        'Authorization': 'Token %s' % settings.IDENTITY_STORE_TOKEN,
        'Content-Type': 'application/json'
    }
    r = requests.get(url, params=params, headers=headers).json()
    while True:
        for optout in r['results']:
            yield optout
        if r.get('next'):
            r = requests.get(r['next'], headers=headers).json()
        else:
            break


def get_messageset_by_shortname(short_name):
    params = {'short_name': short_name}
    r = stage_based_messaging_client.get_messagesets(params=params)
    return next(r["results"])  # messagesets should be unique, return 1st


def get_messageset(messageset_id):
    return stage_based_messaging_client.get_messageset(messageset_id)


def search_messagesets(params):
    r = stage_based_messaging_client.get_messagesets(params=params)
    return r["results"]


def get_schedule(schedule_id):
    return stage_based_messaging_client.get_schedule(schedule_id)


def get_subscriptions(identity):
    """ Gets the active subscriptions for an identity
    """
    params = {'identity': identity, 'active': True}
    return search_subscriptions(params)


def search_subscriptions(params):
    """ Gets the subscriptions based on the params
    """
    r = stage_based_messaging_client.get_subscriptions(params=params)
    return r["results"]


def patch_subscription(subscription, data):
    """ Patches the given subscription with the data provided
    """
    return stage_based_messaging_client.update_subscription(
        subscription["id"], data)


def resend_subscription(subscription_id):
    return stage_based_messaging_client.resend_subscription(subscription_id)


def deactivate_subscription(subscription):
    """ Sets a subscription deactive via a Patch request
    """
    return patch_subscription(subscription, {"active": False})


def get_messageset_short_name(stage, recipient, msg_type, weeks, voice_days,
                              voice_times):

    if recipient == "household":
        msg_type = "audio"

    if stage == "prebirth":
        week_range = "10_42"
    elif stage == "miscarriage":
        week_range = "0_2"
    elif stage == "postbirth":
        if recipient == "household":
            week_range = "0_52"
        elif 0 <= weeks <= 12:
            week_range = "0_12"
        elif 13 <= weeks <= 52:
            week_range = "13_52"
    elif stage == "public":
        week_range = "0_4"

    if msg_type == "text":
        short_name = "%s.%s.%s.%s" % (
            stage, recipient, msg_type, week_range)
    else:
        short_name = "%s.%s.%s.%s.%s.%s" % (
            stage, recipient, msg_type, week_range, voice_days, voice_times)

    return short_name


def get_messageset_schedule_sequence(short_name, weeks):
    # get messageset
    messageset = get_messageset_by_shortname(short_name)

    messageset_id = messageset["id"]
    schedule_id = messageset["default_schedule"]
    # get schedule
    schedule = get_schedule(schedule_id)

    # calculate next_sequence_number
    # get schedule days of week: comma-seperated str e.g. '1,3' for Mon & Wed
    days_of_week = schedule["day_of_week"]
    # determine how many times a week messages are sent e.g. 2 for '1,3'
    msgs_per_week = len(days_of_week.split(','))
    # determine starting message
    # check if in prebirth stage - only starting messaging in week 10
    if 'public' in short_name:
        next_sequence_number = 1  # always start public messages at 1
    elif 'miscarriage' in short_name:
        next_sequence_number = 1  # always start loss messages at 1
    elif 'prebirth' in short_name:
        next_sequence_number = msgs_per_week * (
            weeks - settings.PREBIRTH_MIN_WEEKS)
        if next_sequence_number == 0:
            next_sequence_number = 1  # next_sequence_number cannot be 0
    elif '13_52' in short_name:
        next_sequence_number = msgs_per_week * (weeks - 13)
        if next_sequence_number == 0:
            next_sequence_number = 1  # next_sequence_number cannot be 0
    else:
        next_sequence_number = msgs_per_week * weeks
        if next_sequence_number == 0:
            next_sequence_number = 1  # next_sequence_number cannot be 0

    return (messageset_id, schedule_id, next_sequence_number)


def post_message(payload):
    return message_sender_client.create_outbound(payload)


def get_available_metrics():
    available_metrics = []
    available_metrics.extend(settings.METRICS_REALTIME)
    available_metrics.extend(settings.METRICS_SCHEDULED)

    sources = Source.objects.all()
    for source in sources:
        # only append usernames with characters that are all alphanumeric
        # and/or underscores
        if re.match(r'\w+$', source.user.username):
            available_metrics.append(
                "registrations.source.%s.sum" % source.user.username)

    return available_metrics


def normalise_string(string):
    """ Strips trailing whitespace from string, lowercases it and replaces
        spaces with underscores
    """
    string = (string.strip()).lower()
    return re.sub(r'\W+', '_', string)


def timestamp_to_epoch(timestamp):
    """
    Takes a timestamp and returns a float representing the unix epoch time.
    """
    return (timestamp - datetime.datetime.utcfromtimestamp(0)).total_seconds()


def json_decode(data):
    """
    Decodes the given JSON as primitives
    """
    if isinstance(data, six.binary_type):
        data = data.decode('utf-8')

    return json.loads(data)


def get_language(language):
    return {'english': 'eng_NG',
            'igbo': 'ibo_NG',
            'pidgin': 'pcm_NG'}.get(language, language)


def get_msg_type(msg_type):
    return 'audio' if msg_type == 'voice' else msg_type


def get_voice_times(time):
    return {'9-11am': '9_11',
            '2-5pm': '2_5',
            '6-8pm': '6_8'}.get(time, time)


def get_voice_days(days):
    return {'monday_and_wednesday': 'mon_wed',
            'tuesday_and_thursday': 'tue_thu'}.get(days, days)


def get_receiver(receiver):
    return {
        "mother_and_father": "mother_father",
        "mother_and_family": "mother_family",
        "mother_and_friend": "mother_friend",
    }.get(receiver, receiver)
