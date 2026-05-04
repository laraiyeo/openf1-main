import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone

from loguru import logger

from openf1.services.ingestor_livetiming.core.objects import get_topics
from openf1.services.ingestor_livetiming.real_time.processing import ingest_file
from openf1.services.ingestor_livetiming.real_time.recording import record_to_file
from openf1.util.race_scheduler import is_race_window
from openf1.util.gcs import upload_to_gcs_periodically

TIMEOUT = 5400  # Terminate job if no data received for 90 minutes (in seconds)
GCS_BUCKET = os.getenv("OPENF1_INGESTOR_LIVETIMING_GCS_BUCKET_RAW")
RACE_WINDOW_CHECK_INTERVAL = int(os.getenv("OPENF1_RACE_WINDOW_CHECK_INTERVAL", "60"))


async def main():
    # Create a temporary file that other processes can open (Windows-safe)
    temp = tempfile.NamedTemporaryFile(mode="w", delete=False)
    temp_path = temp.name
    temp.close()
    logger.info(f"Recording raw data to '{temp_path}'")
    tasks = []

    # Record raw data and save it to file
    topics = get_topics()
    logger.info(f"Starting live recording of the following topics: {topics}")
    task_recording = asyncio.create_task(
        record_to_file(
            filepath=temp_path,
            topics=topics,
            timeout=TIMEOUT,
        )
    )
    tasks.append(task_recording)

    if GCS_BUCKET:
        # Save received raw data to GCS, for debugging
        logger.info("Starting periodic GCS upload of raw data")
        gcs_filekey = datetime.now(timezone.utc).strftime("%Y/%m/%d/%H:%M:%S.txt")
        task_upload_raw = asyncio.create_task(
            upload_to_gcs_periodically(
                filepath=temp_path,
                bucket=GCS_BUCKET,
                destination_key=gcs_filekey,
                interval=timedelta(seconds=60),
            )
        )
        tasks.append(task_upload_raw)

    # Ingest received data
    logger.info("Starting data ingestion")
    task_ingest = asyncio.create_task(ingest_file(temp_path))
    tasks.append(task_ingest)

    async def watch_race_window():
        while True:
            await asyncio.sleep(RACE_WINDOW_CHECK_INTERVAL)
            if not is_race_window():
                logger.info(
                    "Race window closed; stopping realtime ingestion tasks and recorder"
                )
                for task in tasks:
                    task.cancel()
                break

    task_race_window = asyncio.create_task(watch_race_window())
    tasks.append(task_race_window)

    try:
        # Wait for any task to stop (recording ends naturally or race window closes)
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        logger.info("Recording stopped")

        # Cancel all the tasks
        logger.info("Stopping tasks")
        for task in tasks:
            task.cancel()

        # Wait for all tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Job completed")
    finally:
        # Clean up the temporary file created earlier
        try:
            os.unlink(temp_path)
            logger.debug(f"Removed temporary file {temp_path}")
        except Exception:
            logger.debug(f"Could not remove temporary file {temp_path}")


if __name__ == "__main__":
    asyncio.run(main())
