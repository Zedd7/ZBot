# -*- coding: utf-8 -*-

from datetime import timedelta

from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

from . import database
from . import utils

MISFIRE_GRACE_TIME = int(timedelta(days=1).total_seconds())

scheduler = AsyncIOScheduler(timezone=utils.TIMEZONE)


def setup(db: database.MongoDBDonnector):
    for collection_name in db.COLLECTION_NAMES:
        jobstore = MongoDBJobStore(database=db.DATABASE_NAME, collection=collection_name, client=db.client)
        scheduler.add_jobstore(jobstore, alias=collection_name)
    scheduler.start()
    print(f"Loaded {len(scheduler.get_jobs())} job(s).")
    scheduler.print_jobs()


def schedule_lottery(timestamp, callback, args):
    job_trigger = DateTrigger(run_date=timestamp)
    job = scheduler.add_job(
        func=callback,
        trigger=job_trigger,
        args=args,
        jobstore='lottery',
        misfire_grace_time=MISFIRE_GRACE_TIME,
        coalesce=False,
        replace_existing=True
    )
    print(f"Scheduled new job : {job}")
    return job
