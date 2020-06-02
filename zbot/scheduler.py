import datetime
from datetime import timedelta

from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from . import database
from . import logger
from . import utils

STORED_JOB_MISFIRE_GRACE_TIME = int(timedelta(days=2).total_seconds())
VOLATILE_JOB_MISFIRE_GRACE_TIME = int(timedelta(hours=2).total_seconds())  # Prevent jobs > 2 hours

scheduler = AsyncIOScheduler(timezone=utils.TIMEZONE)


def setup(db: database.MongoDBConnector):
    for collection_name in dict(filter(lambda i: i[1].get('is_jobstore'), db.COLLECTIONS_CONFIG.items())):
        jobstore = MongoDBJobStore(database=db.database_name, collection=collection_name, client=db.client)
        scheduler.add_jobstore(jobstore, alias=collection_name)
    scheduler.start()
    jobs = scheduler.get_jobs()
    logger.debug(
        f"Loaded {len(jobs)} job(s)" + (f": {', '.join([job.id for job in jobs])}" if jobs else ".")
    )


def get_job_run_date(job_id):
    return scheduler.get_job(job_id).next_run_time


def schedule_stored_job(collection_name, time, callback, *args):
    job = scheduler.add_job(
        func=callback,
        args=args,
        jobstore=collection_name,
        misfire_grace_time=STORED_JOB_MISFIRE_GRACE_TIME,
        next_run_time=time,
        replace_existing=True
    )
    logger.debug(f"Scheduled new stored job of id {job.id} : {job}")
    return job


def reschedule_stored_job(job_id, time):
    job_trigger = DateTrigger(run_date=time)
    scheduler.reschedule_job(job_id, trigger=job_trigger)


def cancel_stored_job(job_id):
    scheduler.remove_job(job_id)
    logger.debug(f"Cancelled job of id : {job_id}")


def schedule_volatile_job(time, callback, *args, interval: datetime.timedelta = None):
    trigger = None
    if interval:
        trigger = IntervalTrigger(seconds=int(interval.total_seconds()))
    job = scheduler.add_job(
        func=callback,
        trigger=trigger,
        args=args,
        misfire_grace_time=VOLATILE_JOB_MISFIRE_GRACE_TIME,
        next_run_time=time,
        replace_existing=True
    )
    return job
