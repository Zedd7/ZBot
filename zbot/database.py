# -*- coding: utf-8 -*-

import os
import sys
import traceback

import pymongo
from pymongo.errors import ConnectionFailure


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
                raise ConnectionFailure("Not MongoDB password found in .env file under the key 'MONGODB_PASSWORD'.")

            self.client = pymongo.MongoClient(f'mongodb+srv://{self.USER_NAME}:{password}@zbot-5waud.gcp.mongodb.net/test?retryWrites=true')
            self.client.admin.command('ismaster')  # Check if connected
            print(f"Connected to MongoDB database '{self.DATABASE_NAME}'.")
            self.connected = True

            self.database = self.client[self.DATABASE_NAME]
            for collection_name in self.COLLECTION_NAMES:
                self.collections[collection_name] = self.database[collection_name]
            print(f"Loaded {len(self.collections)} collection(s).")

        except ConnectionFailure as error:
            print(f"Could not connect to MongoDB database '{self.DATABASE_NAME}'.")
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

        return self.connected
