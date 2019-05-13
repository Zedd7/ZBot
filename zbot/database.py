import os

import pymongo
from pymongo.errors import ConnectionFailure

from . import logger


class MongoDBDonnector:

    USER_NAME = 'Zedd7'
    DATABASE_NAME = 'zbot'
    COLLECTION_NAMES = ['lottery']

    def __init__(self):
        self.client = None
        self.connected = False
        self.database = None
        self.collections = {}

    def open_connection(self):
        try:
            password = os.getenv('MONGODB_PASSWORD')
            if not password:
                raise ConnectionFailure("No MongoDB password found in .env file under the key 'MONGODB_PASSWORD'.")

            self.client = pymongo.MongoClient(f'mongodb+srv://{self.USER_NAME}:{password}@zbot-5waud.gcp.mongodb.net/test?retryWrites=true')
            self.client.admin.command('ismaster')  # Check if connected
            logger.info(f"Connected to MongoDB database '{self.DATABASE_NAME}'.")
            self.connected = True

            self.database = self.client[self.DATABASE_NAME]
            for collection_name in self.COLLECTION_NAMES:
                self.collections[collection_name] = self.database[collection_name]
            logger.info(f"Loaded {len(self.collections)} collection(s).")

        except ConnectionFailure as error:
            logger.error(f"Could not connect to MongoDB database '{self.DATABASE_NAME}'.", exc_info=True)

        return self.connected

    def update_lottery(self, job_id, data):
        self.database['lottery'].update_one({'_id': job_id}, {'$set': data})

    def load_pending_lotteries(self, pending_lotteries):
        data_keys = ['lottery_id', 'message_id', 'channel_id', 'emoji', 'organizer_id', '_id']
        for pending_lottery in self.database['lottery'].find({}, dict.fromkeys(data_keys, 1)):
            pending_lotteries[pending_lottery['message_id']] = {data_key: pending_lottery[data_key] for data_key in data_keys}