import html
import mimetypes
from email.utils import make_msgid
import csv
import os
import re
import smtplib
import time
from email.message import EmailMessage

import requests
from gigachat import GigaChat

MODEL = "GigaChat-2"
GIGA_KEY = "MDFhMjE3MDEtYTczYS03ZTk2LTk1MDUtMDkzZThkODJkYWU2OjVlMDA2YzVhLWIwMGItNGNkMS04N2UyLThmZDg4NzY1YjQxYg==" 
SMTP_HOST = "smtp.yandex.ru"
SMTP_PORT = 465
SMTP_USER = "aguikki@yandex.ru"          
SMTP_PASS = "wcjgwmimfqmszafv"       
DRY_RUN = False         
TEST_EMAIL = "dka.keremyasova13@mail.ru"      
PAUSE_SEC = 20       
IMAGE_FILE = "Vector.png"                         

UNIVERSITY = "АГУИККИ"
EVENT = """
Олимпиада для школьников «Название»
Даты: ...
Формат: ...
Регистрация: https://...
Контакты оргкомитета: ...
"""

SCHOOLS_FILE = "schools.csv"
SENT_FILE = "sent.txt"
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def find_email(site: str) -> str | None:
    base = site.rstrip("/")
    for path in ("", "/contacts", "/contact", "/kontakty", "/sveden/common"):
        try:
            html = requests.get(
                base + path,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"},
            ).text
        except requests.RequestException:
            continue
        found = [
            e for e in EMAIL_RE.findall(html)
            if not e.lower().endswith((".png", ".jpg", ".gif"))
        ]
        if found:
            return found[0]
    return None


def write_letter(giga: GigaChat, school: str) -> str:
    prompt = (
        f"Напиши короткое вежливое письмо от имени университета «{UNIVERSITY}» "
        f"директору школы «{school}». Сообщи о мероприятии для школьников и "
        f"пригласи принять участие. Данные о мероприятии:\n{EVENT}\n"
        "Требования: до 150 слов, без выдуманных фактов, только данные выше, "
        "обращение «Уважаемый руководитель», в конце подпись "
        f"«С уважением, {UNIVERSITY}». Выдай только текст письма."
    )
    return giga.chat(prompt).choices[0].message.content.strip()


def send_mail(to: str, text: str):
    text += "\n\nЕсли вы не хотите получать такие письма, ответьте «Отписаться»."
    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"] = to
    msg["Subject"] = f"{UNIVERSITY}: приглашение для школьников"
    msg.set_content(text) 

    body = html.escape(text).replace("\n", "<br>")
    cid = make_msgid()
    img_tag = ""
    if IMAGE_FILE:
        img_tag = (f'<img src="cid:{cid[1:-1]}" '
        'style="max-width:100%;border-radius:8px;"><br><br>')
        page = f"""<html><body style="margin:0;padding:20px;background:#f4f4f4;">
        <div style="max-width:600px;margin:0 auto;background:#ffffff;padding:24px;
        text-align:center;font-family:Arial,sans-serif;font-size:16px;
        line-height:1.5;color:#222;">
        {img_tag}{body}
        </div></body></html>"""
    msg.add_alternative(page, subtype="html")

    if IMAGE_FILE:
        mime, _ = mimetypes.guess_type(IMAGE_FILE)
        maintype, subtype = (mime or "image/jpeg").split("/")
        with open(IMAGE_FILE, "rb") as f:
            msg.get_payload()[1].add_related(
                f.read(), maintype=maintype, subtype=subtype, cid=cid)

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as s:
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)


def main():
    tested = 0
    sent = (
        set(open(SENT_FILE, encoding="utf-8").read().split())
        if os.path.exists(SENT_FILE)
        else set()
    )

    with GigaChat(
        credentials=GIGA_KEY,
        scope="GIGACHAT_API_PERS",
        model=MODEL,
        verify_ssl_certs=False,
    ) as giga, open(SCHOOLS_FILE, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row["name"]
            email = (row.get("email") or "").strip()
            if not email and row.get("site"):
                email = find_email(row["site"]) or ""
            if not email:
                print(f"[нет почты] {name}")
                continue
            if email in sent and not TEST_EMAIL:
                continue
            if TEST_EMAIL:
                tested += 1
                if tested > 3:   
                    break

            letter = write_letter(giga, name)
            if DRY_RUN:
                print(f"\n--- {name} <{email}> ---\n{letter}\n")
                continue

            try:
                if TEST_EMAIL:
                    send_mail(TEST_EMAIL, f"[ТЕСТ для {name} <{email}>]\n\n" + letter)
                    print(f"[OK] Письмо УСПЕШНО отправлено на {TEST_EMAIL} (тест для: {name})")
                else:
                    send_mail(email, letter)
                    with open(SENT_FILE, "a", encoding="utf-8") as sf:
                        sf.write(email + "\n")
                    print(f"[отправлено] {name} <{email}>")
            except Exception as e:
                print(f"[ошибка] {name}: {e}")
            time.sleep(PAUSE_SEC)


if __name__ == "__main__":
    main()