import datetime
import os
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple

import pymongo
from dateutil.relativedelta import relativedelta
from pymongo.errors import ConnectionFailure

from . import converter
from . import logger


class MongoDBConnector:

    ACCOUNT_DATA_COLLECTION = 'account_data'
    METADATA_COLLECTION = 'metadata'  # Collection of data about bot jobs and data
    PENDING_LOTTERIES_COLLECTION = 'pending_lottery'
    PENDING_POLLS_COLLECTION = 'pending_poll'
    RECRUITMENT_ANNOUNCES_COLLECTION = 'recruitment_announce'
    COLLECTIONS_CONFIG = {
        ACCOUNT_DATA_COLLECTION: {},
        METADATA_COLLECTION: {},
        PENDING_LOTTERIES_COLLECTION: {'is_jobstore': True},
        PENDING_POLLS_COLLECTION: {'is_jobstore': True},
        RECRUITMENT_ANNOUNCES_COLLECTION: {},
    }

    def __init__(self):
        self.client = None
        self.connected = False
        self.database = None
        self.collections = {}
        self.database_host = os.getenv('MONGODB_DATABASE_HOST')
        self.database_name = os.getenv('MONGODB_DATABASE_NAME')

        if not self.database_host:
            raise ConnectionFailure(
                "No MongoDB host found in .env file under the key 'MONGODB_HOST'."
            )
        if not self.database_name:
            raise ConnectionFailure(
                "No MongoDB database name found in .env file under the key 'MONGODB_DATABASE_NAME'."
            )

    def open_connection(self):
        try:
            self.client = pymongo.MongoClient(self.database_host + '?retryWrites=true')
            self.client.admin.command('ismaster')  # Check if connected and raises ConnectionFailure if not
            logger.debug(f"Connected to MongoDB database '{self.database_name}'.")
            self.connected = True

            self.database = self.client[self.database_name]
            for collection_name in self.COLLECTIONS_CONFIG.keys():
                self.collections[collection_name] = self.database[collection_name]
            logger.debug(f"Loaded {len(self.collections)} collection(s).")

        except ConnectionFailure:
            logger.error(
                f"Could not connect to MongoDB database '{self.database_name}'.", exc_info=True
            )

        return self.connected

    # Metadata

    def update_metadata(self, key, value):
        self.database[self.METADATA_COLLECTION].update_one(
            {'_id': key},
            {'$set': {'data': value}},
            upsert=True
        )
        logger.debug(f"Updated metadata '{key}': '{value}'.")

    def get_metadata(self, key):
        if res := self.database[self.METADATA_COLLECTION].find_one({'_id': key}):
            return res['data']
        return None

    # Admin

    def update_recruitment_announces(self, announces):
        upsert_count = 0
        for announce in announces:
            res = self.database[self.RECRUITMENT_ANNOUNCES_COLLECTION].update_one(
                {'_id': announce.id},
                {'$set': {'author': announce.author.id, 'time': announce.created_at}},
                upsert=True
            )
            upsert_count += bool(res.upserted_id)
        logger.debug(f"Inserted or updated {upsert_count} recruitment announce(s).")

    def delete_recruitment_announces_by_author(self, member_id):
        res = self.database[self.RECRUITMENT_ANNOUNCES_COLLECTION].delete_many(
            {'author': member_id}
        )
        logger.debug(f"Deleted {res.deleted_count} recruitment announce(s).")

    def load_recruitment_announces_data(self, query: Dict[str, Any], order: List[Tuple[str, int]]):
        return list(self.database[self.RECRUITMENT_ANNOUNCES_COLLECTION].find(query, sort=order))

    # Lottery, Poll

    def update_job_data(self, collection_name, job_id, data):
        self.database[collection_name].update_one({'_id': job_id}, {'$set': data})

    def delete_job_data(self, collection_name, job_id):
        self.database[collection_name].delete_one({'_id': job_id})

    def load_pending_jobs_data(self, collection_name, pending_jobs_data, data_keys):
        for pending_job in self.database[collection_name].find({}, dict.fromkeys(data_keys, 1)):
            pending_jobs_data[pending_job['message_id']] = dict(pending_job)

    # Messaging

    def update_accounts_data(self, accounts_data):
        upsert_count = 0
        for member, account_data in accounts_data.items():
            res = self.database[self.ACCOUNT_DATA_COLLECTION].update_one(
                {'_id': member.id},
                {'$set': account_data},
                upsert=True
            )
            upsert_count += bool(res.upserted_id)
        logger.debug(f"Inserted or updated {upsert_count} account data.")

    def get_unrecorded_members(self, members):
        accounts_data = self.database[self.ACCOUNT_DATA_COLLECTION].find({}, {'_id': 1})
        account_ids = [account_data['_id'] for account_data in accounts_data]
        return list(filter(lambda m: m.id not in account_ids, members))

    def get_anniversary_account_ids(
            self, reference_date: datetime.datetime, min_account_creation_date: datetime.datetime
    ):
        # Initialize anniversary dates at midnight one year ago
        anniversary_day = converter.GUILD_TIMEZONE.localize(datetime.datetime.combine(
            reference_date.date() - relativedelta(years=1), datetime.time(0, 0)
        ))
        day_after_anniversary = anniversary_day + relativedelta(days=1)

        # Loop over each anniversary and fetch accounts with creation date on that day
        account_anniversaries, display_names = {}, []
        anniversary_years = 1
        while anniversary_day >= min_account_creation_date:
            accounts_data = self.database[self.ACCOUNT_DATA_COLLECTION].find(
                {'creation_date': {
                    '$gt': converter.to_timestamp(anniversary_day),
                    '$lt': converter.to_timestamp(day_after_anniversary)
                }}, {'_id': 1, 'display_name': 1}
            )
            for account_data in accounts_data:
                account_anniversaries.setdefault(anniversary_years, []).append(account_data['_id'])
                display_names.append(account_data['display_name'])
            anniversary_years += 1
            anniversary_day -= relativedelta(years=1)
            day_after_anniversary -= relativedelta(years=1)
        logger.debug(
            f"Found {sum(map(lambda ids: len(ids), account_anniversaries.values()))} "
            f"account anniversaries: {', '.join(display_names)}"
        )
        return account_anniversaries
