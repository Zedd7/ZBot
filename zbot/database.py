import os
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple

import pymongo
from pymongo.errors import ConnectionFailure

from . import logger


class MongoDBConnector:

    DATABASE_NAME = 'zbot'
    RECRUITMENT_ANNOUNCES_COLLECTION = 'recruitment_announce'
    PENDING_LOTTERIES_COLLECTION = 'pending_lottery'
    PENDING_POLLS_COLLECTION = 'pending_poll'
    COLLECTIONS_CONFIG = {
        RECRUITMENT_ANNOUNCES_COLLECTION: {},
        PENDING_LOTTERIES_COLLECTION: {'is_jobstore': True},
        PENDING_POLLS_COLLECTION: {'is_jobstore': True}
    }

    def __init__(self):
        self.client = None
        self.connected = False
        self.database = None
        self.collections = {}

    def open_connection(self):
        try:
            username = os.getenv('MONGODB_USERNAME')
            if not username:
                raise ConnectionFailure(
                    "No MongoDB username found in .env file under the key 'MONGODB_USERNAME'."
                )
            password = os.getenv('MONGODB_PASSWORD')
            if not password:
                raise ConnectionFailure(
                    "No MongoDB password found in .env file under the key 'MONGODB_PASSWORD'."
                )

            self.client = pymongo.MongoClient(f'mongodb+srv://{username}:{password}'
                                              f'@zbot-5waud.gcp.mongodb.net/test?retryWrites=true')
            self.client.admin.command('ismaster')  # Check if connected and raises ConnectionFailure if not
            logger.debug(f"Connected to MongoDB database '{self.DATABASE_NAME}'.")
            self.connected = True

            self.database = self.client[self.DATABASE_NAME]
            for collection_name in self.COLLECTIONS_CONFIG.keys():
                self.collections[collection_name] = self.database[collection_name]
            logger.debug(f"Loaded {len(self.collections)} collection(s).")

        except ConnectionFailure:
            logger.error(
                f"Could not connect to MongoDB database '{self.DATABASE_NAME}'.", exc_info=True
            )

        return self.connected

    # Admin

    async def update_recruitment_announces(self, recruitment_channel):
        upsert_count = 0
        for announce in await recruitment_channel.history().flatten():
            res = self.database[self.RECRUITMENT_ANNOUNCES_COLLECTION].update_one(
                {'_id': announce.id},
                {'$set': {'author': announce.author.id, 'time': announce.created_at}},
                upsert=True
            )
            upsert_count += bool(res.upserted_id)
        logger.debug(f"Inserted {upsert_count} new recruitment announce(s).")

    def load_recruitment_announces_data(self, query: Dict[str, Any], order: List[Tuple[str, int]]):
        return list(self.database[self.RECRUITMENT_ANNOUNCES_COLLECTION].find(query, sort=order))

    # Jobstores

    def update_job_data(self, collection_name, job_id, data):
        self.database[collection_name].update_one({'_id': job_id}, {'$set': data})

    def delete_job_data(self, collection_name, job_id):
        self.database[collection_name].delete_one({'_id': job_id})

    def load_pending_jobs_data(self, collection_name, pending_jobs_data, data_keys):
        for pending_job in self.database[collection_name].find({}, dict.fromkeys(data_keys, 1)):
            pending_jobs_data[pending_job['message_id']] = dict(pending_job)
