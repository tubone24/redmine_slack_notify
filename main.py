import atoma
import requests
import re
import json
from datetime import datetime, timedelta, timezone
from time import sleep

JST = timezone(timedelta(hours=+9))

URL = ""
WEB_HOOK_URL_DAYLY = ""
WEB_HOOK_URL_EACH = ""
LOOP_INTERVAL = 5
DAILY_HOUR = 23
DAILY_MINUTES = 30


def notify_slack_dayly(messages):
    text_prefix = ""
    text_suffix = ""
    text_list = []
    for message in messages:
        bleak_str = "=" * 30
        text = bleak_str + "\n\n番号　　　： `{id}` \n題名　　　： *{title}* \nステータス：{status}\n本文　　　：{content}\n\n".format(id=message["id"], title=message["title"], status=message["status"], content=message["text"])
        text_list.append(text)
    payload = {"text": text_prefix + "\n".join(text_list) + text_suffix}
    requests.post(WEB_HOOK_URL_DAYLY, json.dumps(payload))


def notify_slack_each(messages):
    bleak_str = "=" * 30
    text = bleak_str + "\n\n番号　　　： `{id}` \n題名　　　： *{title}* \nステータス：{status}\n本文　　　：{content}\n\n".format(id=messages[0]["id"], title=messages[0]["title"], status=messages[0]["status"], content=messages[0]["text"])
    payload = {"text": text}
    requests.post(WEB_HOOK_URL_EACH, json.dumps(payload))


def notify_slack_error(error):
    try:
        requests.post(WEB_HOOK_URL_EACH, str(error))
    except Exception:
        pass

def before_3days_msg(messages, now):
    return_msg = []
    for message in messages:
        if message["updated"] > now.astimezone(JST) - timedelta(days=3):
            return_msg.append(message)
    return return_msg


def create_contents_text(text):
    format_text = text.replace("```", "").replace("\n", "").replace(" ","")
    return format_text


def extract_entries(entries):
    notifies = []
    for entry in entries:
        title = entry.title.value
        p1 = re.compile(r"^.+(.+):")
        format_title = p1.sub("", title)
        p2 = re.compile(r"(.+):")
        status = p2.search(title).group()
        id = entry.id_
        updated = entry.updated
        updated_jst = updated.astimezone(JST)
        author_name = entry.authors[0].name
        content = entry.content.value
        p = re.compile(r"<[^>]*?>")
        text = p.sub("", content)
        format_text = create_contents_text(text)
        # print(format_text)
        notifies.append({"title": format_title, "id": id, "updated": updated_jst, "author_name": author_name, "text": format_text, "status": status})
    return notifies


def main():
    now = datetime.now()
    response = requests.get(URL)
    feed = atoma.parse_atom_bytes(response.content)
    now_jst = now.astimezone(JST)
    print(now)

    entries = feed.entries
    notifies = extract_entries(entries)
    updated_jst = notifies[0]["updated"]
    updated_jst = updated_jst.strftime("%Y-%m-%dT%H:%M:%S.%f%z")

    with open("since_db.txt", "r") as f:
        before_updated = f.read()
        print(before_updated)
    if before_updated == updated_jst:
        print("no update! skip")
    else:
        notify_slack_each(notifies)
    with open("since_db.txt", "w") as f:
        print(updated_jst)
        f.write(updated_jst)

    if now_jst.hour == DAILY_HOUR and DAILY_MINUTES < now.minute <= DAILY_MINUTES + LOOP_INTERVAL + 1:
        print("dayly")
        dayly_msg = before_3days_msg(notifies, now)
        notify_slack_dayly(dayly_msg)


def loop_main():
    while True:
        try:
            main()
        except Exception as e:
            notify_slack_error(e)
        sleep(LOOP_INTERVAL * 60)


if __name__ == "__main__":
    loop_main()








