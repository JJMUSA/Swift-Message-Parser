from os import environ as env
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from dotenv import load_dotenv

load_dotenv()


def send_email(subject, body, recipients, attachments=None, inline_images=None,
               cc=None,):
    password = env.get("OUTLOOK_HOST_PASSWORD")
    user = env.get("OUTLOOK_HOST_USER")
    msg = MIMEMultipart('related')
    msg['Subject'] = subject
    msg['From'] = env.get("OUTLOOK_HOST_USER")
    msg['To'] = ', '.join(recipients)
    msg['Cc'] = ', '.join(cc) if cc else None
    msg.attach(MIMEText(body, 'html'))
    if attachments:
        for attachment in attachments:
            with open(f'./Outputfiles/{attachment}', "rb") as f:
                part = MIMEApplication(f.read(), Name=attachment)
            part['Content-Disposition'] = f'attachment; filename="{attachment}"'
            msg.attach(part)
    if inline_images:
        add_images(msg, inline_images)
    smtp_server = smtplib.SMTP(env.get("OUTLOOK_HOST"), timeout=125)
    smtp_server.set_debuglevel(0)
    smtp_server.starttls()
    smtp_server.connect(port=env.get("OUTLOOK_PORT"), host=env.get("OUTLOOK_HOST"))
    smtp_server.starttls()
    smtp_server.set_debuglevel(1)
    smtp_server.login(user, password)
    smtp_server.sendmail(user, recipients+cc, msg.as_string())
    # smtp_server.sendmail(recipients, msg.as_string())
    smtp_server.quit()


def add_images(msg, images):
    for image in images:
        image_id = image.split("/")[-1]
        print(image_id)
        with open(image, "rb") as f:
            img = MIMEImage(f.read(), Name=image)
            img.add_header('Content-ID', f'<{image_id}>')
            # img.add_header('Content-Disposition', 'inline', filename=image)
            msg.attach(img)