from datetime import timedelta
from sqlalchemy import select, text
from app.database.session import SessionLocal, utcnow
from app.models.entities import Incident, EscalationRule, Notification
from app.services.workflow import TERMINAL, notify, escalate, timeline
from app.services.notifications import deliver_email
from app.websocket.manager import manager


def check_sla(db, now=None):
    now = now or utcnow()
    if db.bind.dialect.name == 'postgresql':
        if not db.scalar(text('SELECT pg_try_advisory_xact_lock(774201)')):
            return 0
    count = 0
    policies = list(db.scalars(select(EscalationRule).where(EscalationRule.active.is_(True))))
    for incident in db.scalars(select(Incident).where(Incident.status.not_in(TERMINAL)).with_for_update()):
        remaining = (incident.sla_due_at - now).total_seconds()
        kind = 'SLA_BREACH' if remaining <= 0 else 'SLA_WARNING' if remaining <= 300 else None
        # A reopened incident gets a fresh SLA cycle; older notifications do not suppress it.
        cycle_start = incident.sla_due_at - timedelta(minutes=5)
        if kind and not db.scalar(select(Notification.id).where(Notification.incident_id == incident.id, Notification.type == kind, Notification.created_at >= cycle_start)):
            notify(db, incident, kind, f'{incident.incident_number}: SLA deadline {incident.sla_due_at.isoformat()} UTC')
            timeline(db, incident, None, kind, 'SLA deadline breached' if remaining <= 0 else 'SLA due within five minutes')
            count += 1
        for policy in policies:
            if policy.severity == incident.severity and now >= incident.created_at + timedelta(minutes=policy.after_minutes):
                escalate(db, incident, policy.level, policy.target_role, f'{policy.after_minutes} minute escalation policy')
    db.flush()
    return count


async def scheduled_check():
    with SessionLocal() as db:
        before = set(db.scalars(select(Notification.id)))
        check_sla(db)
        db.commit()
        ids = set(db.scalars(select(Notification.id))) - before
        if ids:
            import asyncio
            await asyncio.to_thread(deliver_email, db, ids)
    await manager.publish()
