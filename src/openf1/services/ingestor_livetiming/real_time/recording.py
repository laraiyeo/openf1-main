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

            # Immediately log whether the recorder created the file and its size
            try:
                init_exists = os.path.exists(filepath)
                init_size = os.path.getsize(filepath) if init_exists else 0
                logger.debug(f"Initial file state: exists={init_exists}, size={init_size}")
            except Exception as e:
                logger.debug(f"Failed to stat initial file {filepath}: {e}")

            # Monitor task: periodically check file for content for a grace period
            async def monitor_file_size():
                try:
                    checks = 8  # total wait = checks * interval (here 8*15 = 120s)
                    interval = 15
                    for i in range(checks):
                        await asyncio.sleep(interval)
                        if proc.returncode is not None:
                            return
                        try:
                            size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
                        except Exception:
                            size = 0
                        logger.debug(f"Monitor check {i+1}/{checks}, size={size}")
                        if size > 0:
                            return

                    # If we get here, the file is still empty after the grace period
                    if proc.returncode is None:
                        logger.warning(
                            f"File '{filepath}' is empty after {checks*interval} seconds. "
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
