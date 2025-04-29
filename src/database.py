# src/database.py

import logging
import os # Added import
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (Boolean, Column, DateTime, Integer, String, Text,
                        create_engine, func)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base # Corrected import

# Ensure this import works relative to the execution context (main.py)
# If running database.py directly, this might fail.
from .config_loader import get_config

log = logging.getLogger(__name__)

Base = declarative_base()


class Job(Base):
    """SQLAlchemy model for storing job postings."""
    __tablename__ = 'jobs'

    id = Column(Integer, primary_key=True)
    company = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False, index=True)
    location = Column(String, index=True)
    url = Column(String, nullable=False, unique=True, index=True)
    description = Column(Text)
    posted_date = Column(DateTime) # Store as UTC
    scraped_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    is_notified = Column(Boolean, default=False, nullable=False, index=True)
    is_applied = Column(Boolean, default=False, nullable=False, index=True)
    is_ignored = Column(Boolean, default=False, nullable=False, index=True)

    def __repr__(self):
        return f"<Job(id={self.id}, company='{self.company}', title='{self.title}', url='{self.url}')>"


engine = None
SessionLocal = None

def init_db() -> bool: # Added return type hint
    """Initializes the database engine and creates tables if they don't exist."""
    global engine, SessionLocal
    config = get_config()
    if not config or 'storage' not in config:
        log.error("Storage configuration not found. Cannot initialize database.")
        return False

    storage_config = config['storage']
    storage_type = storage_config.get('type', 'sqlite')
    # Use os.path.join for robust path construction
    db_path_relative = storage_config.get('path', 'jobs.db')
    # Assume db_path is relative to project root where config.yaml resides
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(project_root, db_path_relative)


    if storage_type != 'sqlite':
        log.error(f"Unsupported storage type '{storage_type}'. Only 'sqlite' is currently supported.")
        # In the future, could add logic for 'txt' or other types here
        return False

    # Ensure the directory for the SQLite file exists
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir, exist_ok=True)
            log.info(f"Created database directory: {db_dir}")
        except OSError as e:
            log.error(f"Error creating database directory '{db_dir}': {e}")
            return False

    db_url = f"sqlite:///{db_path}"
    log.info(f"Initializing database connection to: {db_url}")

    try:
        engine = create_engine(db_url, connect_args={"check_same_thread": False}) # check_same_thread=False needed for SQLite with multiple threads/components
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        log.info(f"Database initialized successfully. DB file: {db_path}")
        return True
    except SQLAlchemyError as e:
        log.error(f"Error initializing database at {db_url}: {e}")
        engine = None
        SessionLocal = None
        return False
    except Exception as e:
        log.error(f"An unexpected error occurred during database initialization: {e}")
        engine = None
        SessionLocal = None
        return False


def get_db():
    """Generator function to get a database session."""
    if not SessionLocal:
        log.error("Database not initialized. Call init_db() first.")
        yield None # Or raise an exception? Yielding None allows callers to handle
        return

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Database Interaction Functions ---

def add_job(job_data: dict) -> Optional[Job]:
    """Adds a new job to the database if it doesn't already exist (based on URL).

    Args:
        job_data: A dictionary containing job details like 'company', 'title', 'url', etc.

    Returns:
        The newly created Job object if added, None otherwise (e.g., if duplicate or error).
    """
    if not SessionLocal:
        log.error("Cannot add job, database not initialized.")
        return None

    db_gen = get_db()
    db = next(db_gen)
    if not db:
        return None

    try:
        # Check if job with the same URL already exists
        existing_job = db.query(Job).filter(Job.url == job_data.get('url')).first()
        if existing_job:
            log.debug(f"Job already exists (URL: {job_data.get('url')}). Skipping.")
            return None # Indicate job was not added because it's a duplicate

        # Ensure required fields are present
        if not all(k in job_data for k in ['company', 'title', 'url']):
             log.warning(f"Skipping job due to missing required fields (company, title, url): {job_data}")
             return None

        new_job = Job(
            company=job_data['company'],
            title=job_data['title'],
            url=job_data['url'],
            location=job_data.get('location'),
            description=job_data.get('description'),
            # TODO: Convert posted_date string to datetime if necessary (needs defined format)
            # posted_date=parse_datetime(job_data.get('posted_date')), # Requires a helper
            scraped_date=datetime.now(timezone.utc) # Explicitly set for clarity
        )

        db.add(new_job)
        db.commit()
        db.refresh(new_job)
        log.info(f"Added new job: {new_job.company} - {new_job.title}")
        return new_job
    except IntegrityError:
        # This case should ideally be caught by the check above, but handles race conditions
        db.rollback()
        log.warning(f"Job already exists (IntegrityError on URL): {job_data.get('url')}")
        return None
    except SQLAlchemyError as e:
        db.rollback()
        log.error(f"Database error adding job: {e}. Data: {job_data}")
        return None
    except Exception as e:
        db.rollback()
        log.error(f"Unexpected error adding job: {e}. Data: {job_data}")
        return None
    finally:
         # Ensure generator is exhausted even on error
        try:
            next(db_gen) # Execute the finally block in get_db
        except StopIteration:
            pass


def get_all_job_urls() -> List[str]:
    """Retrieves a list of all job URLs currently stored in the database."""
    urls = []
    if not SessionLocal:
        log.error("Cannot get job URLs, database not initialized.")
        return urls

    db_gen = get_db()
    db = next(db_gen)
    if not db: return urls

    try:
        results = db.query(Job.url).all()
        urls = [row.url for row in results]
    except SQLAlchemyError as e:
        log.error(f"Database error getting all job URLs: {e}")
    except Exception as e:
        log.error(f"Unexpected error getting all job URLs: {e}")
    finally:
        try: next(db_gen)
        except StopIteration: pass

    return urls


def get_new_jobs_for_notification() -> List[Job]:
    """Retrieves jobs that have not yet been notified.

    Returns:
        A list of Job objects that are not notified, ignored, or applied.
    """
    jobs = []
    if not SessionLocal:
        log.error("Cannot get new jobs, database not initialized.")
        return jobs

    db_gen = get_db()
    db = next(db_gen)
    if not db: return jobs

    try:
        jobs = db.query(Job).filter(
            Job.is_notified == False,
            Job.is_ignored == False, # Don't notify about ignored jobs
            Job.is_applied == False # Optional: Don't re-notify about applied?
        ).order_by(Job.scraped_date.desc()).all() # Or order by posted_date if reliable
    except SQLAlchemyError as e:
        log.error(f"Database error getting new jobs for notification: {e}")
    except Exception as e:
        log.error(f"Unexpected error getting new jobs for notification: {e}")
    finally:
        try: next(db_gen)
        except StopIteration: pass

    return jobs


def mark_job_as_notified(job_id: int) -> bool:
    """Marks a specific job as notified in the database.

    Args:
        job_id: The primary key ID of the job to mark.

    Returns:
        True if the job was successfully marked, False otherwise.
    """
    if not SessionLocal:
        log.error("Cannot mark job as notified, database not initialized.")
        return False

    db_gen = get_db()
    db = next(db_gen)
    if not db: return False

    success = False
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.is_notified = True
            db.commit()
            log.info(f"Marked job ID {job_id} as notified.")
            success = True
        else:
            log.warning(f"Could not mark job as notified: Job ID {job_id} not found.")
    except SQLAlchemyError as e:
        db.rollback()
        log.error(f"Database error marking job ID {job_id} as notified: {e}")
    except Exception as e:
        db.rollback()
        log.error(f"Unexpected error marking job ID {job_id} as notified: {e}")
    finally:
        try: next(db_gen)
        except StopIteration: pass

    return success

# --- Functions for Dashboard ---

def get_dashboard_jobs(filter_applied: bool = False, filter_ignored: bool = False) -> List[Job]:
    """Retrieves jobs for the dashboard, optionally filtering applied/ignored.

    Args:
        filter_applied: If True, only return applied jobs.
        filter_ignored: If True, only return ignored jobs.
                        If both False (default), return active (not applied, not ignored) jobs.

    Returns:
        A list of Job objects matching the filter criteria, ordered by scraped date desc.
    """
    jobs = []
    if not SessionLocal:
        log.error("Cannot get dashboard jobs, database not initialized.")
        return jobs

    db_gen = get_db()
    db = next(db_gen)
    if not db: return jobs

    try:
        query = db.query(Job)
        if filter_applied:
            query = query.filter(Job.is_applied == True)
        elif filter_ignored:
            query = query.filter(Job.is_ignored == True)
        else: # Default: Show active jobs
            query = query.filter(Job.is_applied == False, Job.is_ignored == False)

        # Order by scraped date, newest first
        jobs = query.order_by(Job.scraped_date.desc()).all()

    except SQLAlchemyError as e:
        log.error(f"Database error getting dashboard jobs: {e}")
    except Exception as e:
        log.error(f"Unexpected error getting dashboard jobs: {e}")
    finally:
        try: next(db_gen)
        except StopIteration: pass

    return jobs

def update_job_status(job_id: int, applied: Optional[bool] = None, ignored: Optional[bool] = None) -> bool:
    """Updates the applied or ignored status of a job.

    Args:
        job_id: The ID of the job to update.
        applied: Set to True/False to change applied status.
        ignored: Set to True/False to change ignored status.

    Returns:
        True if the update was successful, False otherwise.
    """
    if not SessionLocal:
        log.error("Cannot update job status, database not initialized.")
        return False
    if applied is None and ignored is None:
        log.warning("No status change provided for update_job_status.")
        return False

    db_gen = get_db()
    db = next(db_gen)
    if not db: return False

    success = False
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            updated = False
            if applied is not None:
                job.is_applied = applied
                # If marking as applied, ensure it's not ignored
                if applied:
                    job.is_ignored = False
                log.info(f"Set job ID {job_id} applied status to: {applied}")
                updated = True
            if ignored is not None:
                job.is_ignored = ignored
                 # If marking as ignored, ensure it's not applied
                if ignored:
                    job.is_applied = False
                log.info(f"Set job ID {job_id} ignored status to: {ignored}")
                updated = True

            if updated:
                db.commit()
                success = True
            else:
                 log.debug(f"No change in status for job ID {job_id}") # Should not happen based on check above
                 success = True # No change needed is also success
        else:
            log.warning(f"Could not update status: Job ID {job_id} not found.")
    except SQLAlchemyError as e:
        db.rollback()
        log.error(f"Database error updating status for job ID {job_id}: {e}")
    except Exception as e:
        db.rollback()
        log.error(f"Unexpected error updating status for job ID {job_id}: {e}")
    finally:
        try: next(db_gen)
        except StopIteration: pass

    return success


# --- TODO: Add functions for ---
# - get_all_jobs (with filtering/pagination for dashboard)
# - mark_job_applied(job_id)
# - mark_job_ignored(job_id)
# - update_job(job_id, data) (if needed)
# - delete_job(job_id) (if needed) 