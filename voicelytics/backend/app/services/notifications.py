import logging
import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage
from sqlalchemy import select
from app.core.config import settings
from app.models.entities import Notification, User, NotificationSetting


class NotificationProvider(ABC):
    @abstractmethod
    def deliver(self, user, notification): ...


class InAppNotificationProvider(NotificationProvider):
    def __init__(self, db):
        self.db = db

    def deliver(self, user, notification):
        notification.user_id = user.id
        self.db.add(notification)


class SMTPEmailProvider(NotificationProvider):
    def deliver(self, user, notification):
        if not settings.smtp_host:
            return
        message = EmailMessage()
        message['Subject'] = notification.title
        message['From'] = settings.smtp_from
        message['To'] = user.email
        message.set_content(notification.message)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_tls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)


def deliver_email(db, ids):
    if not settings.smtp_host:
        return
    provider = SMTPEmailProvider()
    for n in db.scalars(select(Notification).where(Notification.id.in_(ids))):
        preference = db.scalar(select(NotificationSetting).where(NotificationSetting.user_id == n.user_id))
        if preference and preference.email_enabled:
            try:
                provider.deliver(db.get(User, n.user_id), n)
            except (OSError, smtplib.SMTPException):
                logging.exception('Email delivery failed for notification %s; in-app notification retained', n.id)
