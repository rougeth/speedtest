import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

import schedule
from loguru import logger


OUTPUT_FOLDER = Path(os.environ.get("OUTPUT_FOLDER", ""))


def job_speed_test():
    logger.info("Job started: job_speed_test")
    try:
        output = subprocess.check_output("speedtest-cli --json", encoding="utf-8", shell=True)
    except subprocess.CalledProcessError:
        logger.exception("speedtest-cli call failed")
        return

    filename = "{:%Y%m%d-%H%M}.json".format(datetime.now())
    with (OUTPUT_FOLDER / filename).open("w") as fp:
        fp.write(output)
    logger.info("Job finished: job_speed_test")


if __name__ == "__main__":
    logger.info("Starting speedtest app")
    logger.info(f"Output folder: {OUTPUT_FOLDER}")
    logger.info("Starting scheduler")
    schedule.every(10).minutes.do(job_speed_test).run()
    while True:
        schedule.run_pending()
        time.sleep(1)

