#!/usr/bin/python
# -*- coding: utf-8 -*-
"""The script that access the Redmine server in the private environment, detects ticket updates, and notifies Slack.

     * Access the Redmine Server and download issues.csv
     * Parse issues.csv and check any updates
     * When updates, extract contents and push notify to Slack incoming webhook
     * Set the daily time on your config, aggregate all issues and notify all issues by 3days before

Todo:
    * Any Tests
    * Documents
    * Install manual for Raspberry PI

"""

import json
import csv
import re
import textwrap
from datetime import datetime, timedelta, timezone
from time import sleep
import os
from os.path import join, dirname
from dotenv import load_dotenv
import requests
import atoma
from retrying import retry

dotenv_path = join(dirname(__file__), "../.env")
load_dotenv(dotenv_path)

JST = timezone(timedelta(hours=+9))

SINCEDB_PATH = join(dirname(__file__), "../since_db.txt")
ISSUE_CSV_PATH = join(dirname(__file__), "../issues.csv")
CSV_URL = os.environ.get("CSV_URL")
ATOM_URL = os.environ.get("ATOM_URL")
ATOM_KEY = os.environ.get("ATOM_KEY")
WEB_HOOK_URL_DAILY = os.environ.get("WEB_HOOK_URL_DAILY")
WEB_HOOK_URL_EACH = os.environ.get("WEB_HOOK_URL_EACH")
LOOP_INTERVAL = int(os.environ.get("LOOP_INTERVAL"))
DAILY_HOUR = int(os.environ.get("DAILY_HOUR"))
DAILY_MINUTES = int(os.environ.get("DAILY_MINUTES"))


def create_summary_text(row):
    """Creating summary text by latest notes or description.

    If there is the latest note in the Redmine ticket, get the note, otherwise, get the description.

    Args:
        row(OrderDict): Redmine's ticket row

    Returns:
        str: formatted summary text
    """
    content_text = ""
    if "最新の注記" not in row:
        atom_content = get_single_issue_by_atom(row["#"])
        if atom_content:
            return atom_content
        elif row["説明"] != "":
            content_text = "【新規】" + row["説明"]
    else:
        if row["最新の注記"] != "":
            content_text = "【更新】" + row["最新の注記"]
        elif row["説明"] != "":
            content_text = "【新規】" + row["説明"]
    return wrap_long_text(sanitize_contents_text(content_text))


@retry(stop_max_attempt_number=3, wait_incrementing_start=1000, wait_incrementing_increment=1000)
def get_single_issue_by_atom(issue_id):
    url = ATOM_URL + "issues" + "/" + issue_id + ".atom" + "?key=" + ATOM_KEY
    response = requests.get(url, timeout=(3.0, 7.5))
    print(url)
    feed = atoma.parse_atom_bytes(response.content)
    if feed.entries is None or len(feed.entries) == 0:
        return False
    latest_entry = feed.entries[-1]
    author = latest_entry.authors[0].name
    content = sanitize_html_tag(latest_entry.content.value)
    return wrap_long_text("【更新】【{author}】 {content}".format(author=author, content=content))


def sanitize_html_tag(content):
    p = re.compile(r"<[^>]*?>")
    text = p.sub("", content)
    return sanitize_contents_text(text)


def wrap_long_text(text):
    """Wrap long text for slack display

    Args:
        text(text): Long Text

    Returns:
        str: wrapped text

    """
    text_list = textwrap.wrap(text, 40)
    return "\n　　　　　　".join(text_list)


@retry(stop_max_attempt_number=3, wait_incrementing_start=1000, wait_incrementing_increment=1000)
def call_slack_api(webhook, payload):
    """Call Slack incoming Webhook

    Args:
        webhook(str): WEBHOOK URL
        payload(dict): Payload dictionary

    Returns:

    """
    requests.post(webhook, json.dumps(payload), timeout=(3.0, 7.5))


def notify_slack_daily(rows, now):
    text_prefix = "デイリーRedmine更新チケットまとめ\n\n"
    text_suffix = "\n\n\n`更新時間:{now_time}`".format(now_time=now.strftime("%Y-%m-%dT%H:%M:%S.%f%z"))
    text_list = []
    for row in rows:
        content_text = sanitize_contents_text(create_summary_text(row))
        bleak_str = "=" * 60
        text = bleak_str + "\n\n番号　　　： `{id}` \n題名　　　： *{title}* \n" \
                           "ステータス：{status}\n担当者　　：{person}\n更新日　　：{updated}\n" \
                           "概要/状況 ：{content}\n\n".format(id=row["#"],
                                                         title=row["題名"],
                                                         status=row["ステータス"],
                                                         person=row["担当者"],
                                                         updated=row["更新日"],
                                                         content=content_text)
        text_list.append(text)
    payload = {"text": text_prefix + "\n".join(text_list) + text_suffix}
    call_slack_api(WEB_HOOK_URL_DAILY, payload)


def notify_slack_each(rows):
    bleak_str = "=" * 60
    text_prefix = "REDMINEの更新を検知\n\n"
    content_text = create_summary_text(rows[0])
    text = bleak_str + "\n\n番号　　　： `{id}` \n題名　　　： *{title}* \n" \
                       "ステータス：{status}\n担当者　　：{person}\n更新日　　：{updated}\n" \
                       "概要/状況 ：{content}\n\n".format(id=rows[0]["#"],
                                                     title=rows[0]["題名"],
                                                     status=rows[0]["ステータス"],
                                                     person=rows[0]["担当者"],
                                                     updated=rows[0]["更新日"],
                                                     content=content_text)
    payload = {"text": text_prefix + text}
    call_slack_api(WEB_HOOK_URL_EACH, payload)


def notify_slack_error(error):
    try:
        print(error)
        payload = {"text": "*ERROR OCCURRED!!*" + "```" + str(error) + "```"}
        call_slack_api(WEB_HOOK_URL_EACH, payload)
    except Exception:
        print("unhandled ERROR")


def before_3days_msg(rows, now):
    return_msg = []
    for row in rows:
        print(row)
        updated = datetime.strptime(row["更新日"], '%Y/%m/%d %H:%M').astimezone(JST)
        if updated > now.astimezone(JST) - timedelta(days=3):
            return_msg.append(row)
    return return_msg


def sanitize_contents_text(text):
    format_text = text.replace("```", "").replace("\n", "").replace(" ", "").replace("`", "")
    return format_text


# def extract_entries(entries):
#     notifies = []
#     for entry in entries:
#         title = entry.title.value
#         p1 = re.compile(r"^.+(.+):")
#         format_title = p1.sub("", title)
#         p2 = re.compile(r"(.+):")
#         status = p2.search(title).group()
#         id = entry.id_
#         updated = entry.updated
#         updated_jst = updated.astimezone(JST)
#         author_name = entry.authors[0].name
#         content = entry.content.value
#         p = re.compile(r"<[^>]*?>")
#         text = p.sub("", content)
#         format_text = sanitize_contents_text(text)
#         # print(format_text)
#         notifies.append({"title": format_title, "id": id, "updated": updated_jst,
#         "author_name": author_name, "text": format_text, "status": status})
#     return notifies


@retry(stop_max_attempt_number=3, wait_incrementing_start=1000, wait_incrementing_increment=1000)
def download_issues_csv():
    response = requests.get(CSV_URL, timeout=(3.0, 7.5))
    with open(ISSUE_CSV_PATH, 'wb') as saveFile:
        saveFile.write(response.content)


def load_issues_csv():
    with open(ISSUE_CSV_PATH, "r", encoding="utf-8_sig") as f:
        rows = []
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
        return rows


def latest_update(rows):
    tdatetime = datetime.strptime(rows[0]["更新日"], '%Y/%m/%d %H:%M')
    return tdatetime


def is_need_update(updated):
    with open(SINCEDB_PATH, "r") as f:
        last_updated = f.read()
        print("last_updated: {last_updated}".format(last_updated=updated))
        if last_updated == updated:
            return False
        return True


def update_sincedb(updated):
    with open(SINCEDB_PATH, "w") as f:
        f.write(updated)


def check_daily_time(now):
    if now.hour == DAILY_HOUR and DAILY_MINUTES < now.minute <= DAILY_MINUTES + LOOP_INTERVAL:
        return True
    return False


def main():
    now = datetime.now()
    download_issues_csv()
    rows = load_issues_csv()

    now_jst = now.astimezone(JST)
    updated_jst = latest_update(rows)
    updated_jst = updated_jst.strftime("%Y-%m-%dT%H:%M:%S.%f%z")
    if is_need_update(updated_jst):
        notify_slack_each(rows)
        update_sincedb(updated_jst)
    else:
        print("no update! skip")

    if check_daily_time(now_jst):
        print("daily")
        daily_msg = before_3days_msg(rows, now)
        print(daily_msg)
        notify_slack_daily(daily_msg, now)


def loop_main():
    while True:
        try:
            main()
        except Exception as e:
            notify_slack_error(e)
        sleep(LOOP_INTERVAL * 60)


if __name__ == "__main__":
    loop_main()
