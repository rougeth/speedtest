import io
import json
import os
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

import click
import matplotlib.dates as md
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import pandas as pd
import schedule
import telebot
from loguru import logger


REPORTS_PATH = ""
telegram = telebot.TeleBot("invalid-token", threaded=False, skip_pending=True)


def reports(f):
    def wrapper(path, *args, **kwargs):
        logger.info(f"Starting new report. report={f!r}, path={path!r}")
        reports = sorted(path.iterdir(), reverse=True)
        reports = filter(f, reports)

        data = []
        for file in reports:
            try:
                data.append(json.load(file.open()))
            except json.decoder.JSONDecodeError:
                logger.error(f"Erro while opening file. file={file.name!r}")
        logger.info(f"Report loaded. total={len(data)}")
        return data

    return wrapper


@reports
def report_today(file):
    today = datetime.now().strftime("%Y%m%d")
    return file.name.startswith(today)


@reports
def report_last_week(file):
    last_week = datetime.now() - timedelta(days=7)
    last_week = last_week.strftime("%Y%m%d")
    return file.name > last_week


def dashboard_download_upload_ping(data):
    if not data:
        return False

    df = pd.DataFrame(data)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["download"] = df["download"].apply(lambda x: (x / 10 ** 6))
    df["upload"] = df["upload"].apply(lambda x: (x / 10 ** 6))

    plt.grid(color="black", linestyle="-.", linewidth=0.7)
    fig = plt.figure(tight_layout=True)
    gs = gridspec.GridSpec(2, 1)

    plots = [
        {
            "ylabel": "mbps",
            "plots": [
                ("timestamp", "download", "Download"),
                ("timestamp", "upload", "Upload"),
            ],
        },
        {
            "ylabel": "ms",
            "xlabel": "date",
            "plots": [("timestamp", "ping", "Ping")],
        },
    ]

    for i, plot in enumerate(plots):
        ax = fig.add_subplot(gs[i, 0])
        for x, y, label in plot["plots"]:
            ax.plot(df[x], df[y], label=label)

        ax.set_ylabel(plot["ylabel"])
        ax.xaxis.set_major_formatter(md.DateFormatter("%H:%M"))
        for tick in ax.get_xticklabels():
            tick.set_rotation(45)
        ax.grid()
        if plot.get("xlabel"):
            ax.set_xlabel("date")

    return fig


def dashboard_today(reports_path):
    data = report_today(reports_path)
    return dashboard_download_upload_ping(data)


def dashboard_last_week(reports_path):
    data = report_last_week(reports_path)
    return dashboard_download_upload_ping(data)


def job_speed_test(path):
    logger.info("Job started: job_speed_test")
    try:
        output = subprocess.check_output(
            "speedtest-cli --json", encoding="utf-8", shell=True
        )
    except subprocess.CalledProcessError:
        logger.exception("speedtest-cli call failed")
        return

    filename = "{:%Y%m%d-%H%M}.json".format(datetime.now())
    with (path / filename).open("w") as fp:
        fp.write(output)
    logger.info("Job finished: job_speed_test")


def from_plot_to_image(plot):
    buf = io.BytesIO()
    plot.savefig(buf, format="png")
    buf.seek(0)
    return buf


@telegram.message_handler(commands=["today"])
def bot_today(message):
    global REPORTS_PATH
    plot = dashboard_today(REPORTS_PATH)
    if not plot:
        telegram.send_message(message.chat.id, "No data available")
        return

    telegram.send_photo(message.chat.id, from_plot_to_image(plot))


@telegram.message_handler(commands=["last_week"])
def bot_last_week(message):
    global REPORTS_PATH
    plot = dashboard_last_week(REPORTS_PATH)
    if not plot:
        telegram.send_message(message.chat.id, "No data available")
        return

    telegram.send_photo(message.chat.id, from_plot_to_image(plot))


@click.group()
def cli():
    pass


@cli.command()
@click.option('--path', required=True, help="Path of speed test reports")
@click.option('--token', required=True, help="Telegram API token")
def bot(token, path):
    global REPORTS_PATH
    REPORTS_PATH = Path(path)
    telegram.token = token
    telegram.polling()


@cli.command()
@click.option('--path', required=True, help="Path of speed test reports")
def monitor(token, path):
    global REPORTS_PATH
    REPORTS_PATH = Path(path)

    logger.info("Starting speedtest app")
    logger.info(f"Output folder: {REPORTS_PATH}")
    logger.info("Starting scheduler")
    schedule.every(10).minutes.do(job_speed_test, path=REPORTS_PATH).run()
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    cli()