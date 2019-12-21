from datetime import timedelta

from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

from . import database
from . import logger
from . import utils

MISFIRE_GRACE_TIME = int(timedelta(days=2).total_seconds())

scheduler = AsyncIOScheduler(timezone=utils.TIMEZONE)


def setup(db: database.MongoDBConnector):
    for collection_name in db.COLLECTION_NAMES:
        jobstore = MongoDBJobStore(database=db.DATABASE_NAME, collection=collection_name, client=db.client)
        scheduler.add_jobstore(jobstore, alias=collection_name)
    scheduler.start()
    logger.info(f"Loaded {len(scheduler.get_jobs())} job(s).")


def get_job_run_date(job_id):
    return scheduler.get_job(job_id).next_run_time


def schedule_lottery(time, callback, *args):
    job_trigger = DateTrigger(run_date=time)
    job = scheduler.add_job(
        func=callback,
        trigger=job_trigger,
        args=args,
        jobstore='lottery',
        misfire_grace_time=MISFIRE_GRACE_TIME,
        coalesce=False,
        replace_existing=True
    )
    logger.debug(f"Scheduled new lottery job of id {job.id} : {job}")
    return job


def reschedule_lottery(job_id, time):
    job_trigger = DateTrigger(run_date=time)
    scheduler.reschedule_job(job_id, trigger=job_trigger)


def cancel_lottery(job_id):
    scheduler.remove_job(job_id)
    logger.debug(f"Cancelled lottery job of id : {job_id}")
