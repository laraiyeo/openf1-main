import asyncio
import os
import random
import sys

from loguru import logger


async def record_to_file(filepath: str, topics: list[str], timeout: int):
    """Records raw F1 data to a file, using a slightly modified version of the FastF1
    live timing module (https://github.com/br-g/fastf1-livetiming)
    """
    F1_TOKEN = os.getenv("F1_TOKEN")

    while True:
        try:
            command = (
                [sys.executable, "-m", "fastf1_livetiming", "save", filepath]
                + sorted(list(topics))
                + (["--auth"] if F1_TOKEN is not None else [])
                + ["--timeout", str(timeout)]
            )
            logger.debug(f"Starting recorder subprocess: {command}")
            proc = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Monitor task: wait 60 seconds and check if file is being written to
            async def monitor_file_size():
                try:
                    await asyncio.sleep(60)
                    if proc.returncode is None:  # If the process is still running
                        if (
                            not os.path.exists(filepath)
                            or os.path.getsize(filepath) == 0
                        ):
                            logger.warning(
                                f"File '{filepath}' is empty after 1 minute. "
                                "Killing subprocess to trigger a restart."
                            )
                            try:
                                proc.kill()
                            except ProcessLookupError:
                                pass
                except asyncio.CancelledError:
                    pass

            monitor_task = asyncio.create_task(monitor_file_size())

            # Wait for the process to complete and capture output
            stdout, stderr = await proc.communicate()
            monitor_task.cancel()

            # Decode subprocess output for logging
            try:
                out_str = stdout.decode("utf-8").strip() if stdout else ""
            except Exception:
                out_str = "<could not decode stdout>"
            try:
                err_str = stderr.decode("utf-8").strip() if stderr else ""
            except Exception:
                err_str = "<could not decode stderr>"

            if out_str:
                logger.debug(f"Recorder stdout: {out_str}")
            if err_str:
                logger.debug(f"Recorder stderr: {err_str}")

            # Check if the process exited cleanly with an exit code of 0.
            if proc.returncode == 0:
                logger.info("Recorder subprocess completed successfully.")
                break
            else:
                logger.error(
                    f"Recorder subprocess failed with exit code {proc.returncode}."
                )
        except Exception:
            logger.exception(
                "An unexpected exception occurred while trying to run "
                "the recorder subprocess."
            )

        logger.info("Waiting before restarting the recorder...")
        await asyncio.sleep(
            random.uniform(1, 5)
        )  # Use random jitter to prevent synchronized retry loops
