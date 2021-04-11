import io
import json
import os
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from pprint import pprint
import tarfile

import click
import matplotlib.dates as md
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import pandas as pd
import schedule
import seaborn as sns
import telebot
from loguru import logger


ALLOWED_IDS = []
REPORTS_PATH = ""
FREQUENCY = int(os.environ.get("FREQUENCY", 10))
telegram = telebot.TeleBot("invalid-token", threaded=False, skip_pending=True)


def dict_item_or_value(item, key, multiplier=1):
    if isinstance(item, dict):
        return item[key] * multiplier

    return item


def reports(f):
    def wrapper(path, *args, **kwargs):
        logger.info(f"Starting new report. report={f!r}, path={path!r}")
        with tarfile.open(path) as archive:
            files = archive.getmembers()

            reports = sorted(files, key=lambda f: f.name, reverse=True)
            reports = filter(lambda f: not "/._" in f.name, reports)
            reports = filter(f, reports)

            data = []
            for file in reports:
                report = archive.extractfile(file.name)
                try:
                    data.append(json.load(report))
                except json.decoder.JSONDecodeError:
                    logger.exception(f"Erro while opening file. file={file.name!r}")
            logger.info(f"Report loaded. total={len(data)}")
            return data

    return wrapper


@reports
def report_today(file):
    today = datetime.now().strftime("%Y%m%d")
    return today in file.name


@reports
def report_last_week(file):
    name = file.name.split("/")[-1]
    last_week = datetime.now() - timedelta(days=7)
    last_week = last_week.strftime("%Y%m%d")
    return name > last_week


def dashboard_download_upload_ping(data, date_formatter):
    if not data:
        return False

    df = pd.DataFrame(data)

    # Required for migration from speedtest-cli to the SpeedTest CLI by Ookla
    df["download"] = df["download"].apply(lambda x: dict_item_or_value(x, "bandwidth", 8))
    df["upload"] = df["upload"].apply(lambda x: dict_item_or_value(x, "bandwidth", 8))
    df["ping"] = df["ping"].apply(lambda x: dict_item_or_value(x, "latency"))

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["download"] = df["download"].apply(lambda x: (x / 10 ** 6))
    df["upload"] = df["upload"].apply(lambda x: (x / 10 ** 6))

    sns.set_style("ticks")
    fig = plt.figure(tight_layout=True)
    gs = gridspec.GridSpec(2, 1)

    plots = [
        {
            "ylabel": "mbps",
            "plots": [
                ("timestamp", "download", "Download", "#3d5a80"),
                ("timestamp", "upload", "Upload", "#98c1d9"),
            ],
        },
        {
            "ylabel": "ms",
            "xlabel": "date",
            "plots": [("timestamp", "ping", "Ping", "#ee6c4d")],
        },
    ]

    for i, plot in enumerate(plots):
        ax = fig.add_subplot(gs[i, 0])
        for x, y, label, color in plot["plots"]:
            sns.lineplot(data=df, x=x, y=y, ax=ax, color=color)

        sns.despine()
        ax.set_ylabel(plot["ylabel"])
        ax.xaxis.set_major_formatter(md.DateFormatter(date_formatter))
        for tick in ax.get_xticklabels():
            tick.set_rotation(45)
        ax.grid()
        if plot.get("xlabel"):
            ax.set_xlabel("date")
        else:
            ax.set_xlabel("")


    return fig


def dashboard_today(reports_path):
    data = report_today(reports_path)
    return dashboard_download_upload_ping(data, "%H:%M")


def dashboard_last_week(reports_path):
    data = report_last_week(reports_path)
    return dashboard_download_upload_ping(data, "%d %b")


def job_speed_test(path):
    logger.info("Job started: job_speed_test")
    try:
        output = subprocess.check_output(
            "speedtest --accept-gdpr --accept-license --format json", encoding="utf-8", shell=True
        )
    except subprocess.CalledProcessError:
        logger.exception("speedtest-cli call failed")
        return

    data = json.loads(output)
    download = data["download"]["bandwidth"] * 8 / 10 ** 6
    upload = data["upload"]["bandwidth"] * 8 / 10 ** 6
    logger.info(f"Download={download:.2f}Mbps, Upload={upload:.2f}Mbps, Ping={data['ping']!r}")

    filename = "{:%Y%m%d-%H%M}.json".format(datetime.now())
    with tarfile.open(path, mode="a") as tar:
        output = output.encode("utf-8")
        file = io.BytesIO(output)
        tarinfo = tarfile.TarInfo(name=filename)
        tarinfo.mtime = time.time()
        tarinfo.size = len(output)

        tar.addfile(tarinfo, fileobj=file)
    logger.info("Job finished: job_speed_test")


def from_plot_to_image(plot):
    buf = io.BytesIO()
    plot.savefig(buf, format="png")
    buf.seek(0)
    return buf


@telegram.message_handler(commands=["today"])
def bot_today(message):
    if message.chat.id not in ALLOWED_IDS:
        return

    global REPORTS_PATH
    plot = dashboard_today(REPORTS_PATH)
    if not plot:
        telegram.send_message(message.chat.id, "No data available")
        return

    telegram.send_photo(message.chat.id, from_plot_to_image(plot))


@telegram.message_handler(commands=["last_week"])
def bot_last_week(message):
    if message.chat.id not in ALLOWED_IDS:
        return

    global REPORTS_PATH
    plot = dashboard_last_week(REPORTS_PATH)
    if not plot:
        telegram.send_message(message.chat.id, "No data available")
        return

    telegram.send_photo(message.chat.id, from_plot_to_image(plot))


@telegram.message_handler(commands=["myid"])
def bot_myid(message):
    telegram.send_message(message.chat.id, message.chat.id)


@click.group()
def cli():
    pass


@cli.command()
@click.option("--path", required=True, help="Path of speed test reports")
@click.option("--token", required=True, help="Telegram API token")
@click.option(
    "--id",
    type=int,
    multiple=True,
    help="User ID on Telegram allowed to see the reports",
)
def bot(id, token, path):
    global REPORTS_PATH, ALLOWED_IDS
    REPORTS_PATH = Path(path)
    ALLOWED_IDS = id
    telegram.token = token
    telegram.polling()


@cli.command()
@click.option("--path", required=True, help="Path of speed test reports")
def monitor(path):
    global REPORTS_PATH
    REPORTS_PATH = Path(path)

    logger.info("Starting speedtest app")
    logger.info(f"Output folder: {REPORTS_PATH}")
    logger.info("Starting scheduler")
    schedule.every(FREQUENCY).minutes.do(job_speed_test, path=REPORTS_PATH).run()
    while True:
        schedule.run_pending()
        time.sleep(1)


@cli.command()
def test():
    output = subprocess.check_output(
        "speedtest --accept-gdpr --accept-license --format json", encoding="utf-8", shell=True
    )
    output = json.loads(output)

    download = output["download"]["bandwidth"] * 8 / 10 ** 6
    upload = output["upload"]["bandwidth"] * 8 / 10 ** 6

    click.echo(f"Download: {download:.2f}Mbps")
    click.echo(f"Upload: {upload:.2f}Mbps")
    click.echo(f"Ping: {output['ping']}")
    click.echo(f"")
    pprint(output)


@cli.command()
@click.option("--path", required=True, help="Path of speed test reports")
def report(path):
    plot = dashboard_last_week(Path(path))
    plot.savefig("output_last_week.png")

    plot = dashboard_today(Path(path))
    plot.savefig("output_today.png")


if __name__ == "__main__":
    cli()
