from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select
from app.models.entities import *
from app.database.session import utcnow
from app.core.security import role_name, require_role, MANAGERS, WORKERS
from app.repositories.access import get_machine, machine_factory, get_incident
from app.rules.engine import evaluate
from app.utils.serialization import record

TERMINAL = {'RESOLVED', 'VERIFIED', 'CLOSED'}


def audit(db, user, entity, action, old=None, ip=''):
    db.add(AuditLog(user_id=user.id if user else None, entity_type=entity.__tablename__, entity_id=entity.id,
                    action=action, old_value=old, new_value=record(entity), ip_address=ip))


def timeline(db, incident, user, action, description):
    db.add(IncidentAction(incident_id=incident.id, user_id=user.id if user else None, action_type=action, description=description))


def recipients(db, incident, roles=None):
    factory_id = db.get(Report, incident.report_id).factory_id
    users = list(db.scalars(select(User).where(User.is_active.is_(True), User.factory_id == factory_id)))
    if roles:
        return [u for u in users if role_name(db, u) in roles]
    return [u for u in users if u.id == incident.assigned_user_id or u.department_id == incident.assigned_department_id or role_name(db, u) in MANAGERS]


def notify(db, incident, kind, message, users=None):
    for user in users if users is not None else recipients(db, incident):
        db.add(Notification(user_id=user.id, incident_id=incident.id, type=kind, title=f'{incident.incident_number} · {kind.replace("_", " ")}', message=message))


def refresh_machine(db, machine_id):
    db.flush()
    machine = db.get(Machine, machine_id)
    incidents = list(db.scalars(select(Incident).where(Incident.machine_id == machine_id, Incident.status.not_in(TERMINAL))))
    latest = db.scalar(select(MachineLog).where(MachineLog.machine_id == machine_id).order_by(MachineLog.timestamp.desc()))
    if any(i.severity == 'CRITICAL' for i in incidents):
        machine.status = 'CRITICAL'
    elif incidents:
        machine.status = 'WARNING'
    elif latest and latest.status_code in {'OFFLINE', 'STOPPED'}:
        machine.status = 'OFFLINE'
    else:
        machine.status = 'OPERATIONAL'


def escalate(db, incident, level, target_role, reason, actor=None):
    users = recipients(db, incident, {target_role})
    for user in users:
        exists = db.scalar(select(Escalation).where(Escalation.incident_id == incident.id, Escalation.level == level, Escalation.escalated_to == user.id))
        if not exists:
            db.add(Escalation(incident_id=incident.id, level=level, escalated_to=user.id, reason=reason))
            notify(db, incident, 'ESCALATION', reason, [user])
            timeline(db, incident, actor, 'ESCALATION', f'Level {level}: {user.name}. {reason}')
    return users


def create_report(db, user, payload, data=None):
    machine = get_machine(db, user, payload.machine_id)
    station = db.get(Station, machine.station_id)
    line = db.get(ProductionLine, station.production_line_id)
    if payload.shift_id:
        shift = db.get(Shift, payload.shift_id)
        if not shift or shift.factory_id != line.factory_id:
            raise HTTPException(422, 'Shift must belong to the selected factory')
    result = evaluate(db, data or {'text': payload.description + ' ' + payload.transcript}, machine)
    if payload.severity_override:
        require_role(db, user, MANAGERS)
        result['reasons'].append(f'Authorized override by {user.name}: {result["severity"]} → {payload.severity_override}')
        result['severity'] = payload.severity_override
    report = Report(reporter_id=user.id, factory_id=line.factory_id, production_line_id=line.id,
                    station_id=station.id, machine_id=machine.id, shift_id=payload.shift_id,
                    input_type=payload.input_type, transcript=payload.transcript, description=payload.description, language=payload.language)
    db.add(report)
    db.flush()
    report.report_number = f'RPT-{utcnow().year}-{report.id:06d}'
    category = db.scalar(select(IssueCategory).where(IssueCategory.name == result['category'], IssueCategory.active.is_(True)))
    department = db.scalar(select(Department).where(Department.name == result['responsible_department']))
    if not category or not department:
        raise HTTPException(422, 'Rule references an unavailable category or department')
    candidates = list(db.scalars(select(User).where(User.factory_id == line.factory_id, User.department_id == department.id, User.is_active.is_(True)).order_by(User.id)))
    assignee = next((u for u in candidates if role_name(db, u) == 'Engineer'), next((u for u in candidates if role_name(db, u) in WORKERS), None))
    policy = db.scalar(select(SLAPolicy).where(SLAPolicy.severity == result['severity']))
    if not policy:
        raise HTTPException(422, 'Configure an SLA policy for this severity')
    incident = Incident(report_id=report.id, machine_id=machine.id, category_id=category.id, severity=result['severity'],
                        priority=result['priority'], status='ASSIGNED', assigned_department_id=department.id,
                        assigned_user_id=assignee.id if assignee else None, sla_due_at=utcnow() + timedelta(minutes=policy.minutes),
                        matched_rule_ids=result['matched_rule_ids'], classification=result)
    db.add(incident)
    db.flush()
    incident.incident_number = f'INC-{utcnow().year}-{incident.id:06d}'
    timeline(db, incident, user, 'REPORTED', f'{report.report_number}: {payload.description}')
    for match in result['matches']:
        timeline(db, incident, None, 'RULE_MATCHED', f'Rule #{match["rule_id"]} {match["name"]}: {"; ".join(match["reasons"])}')
    timeline(db, incident, user, 'ASSIGNED', f'Assigned to {department.name}' + (f' / {assignee.name}' if assignee else ' department queue'))
    notify(db, incident, 'NEW_INCIDENT', payload.description)
    notify(db, incident, 'ASSIGNMENT', f'Assigned to {department.name}')
    if result['severity'] == 'CRITICAL':
        notify(db, incident, 'CRITICAL_ALERT', payload.description)
    if result['escalation_required']:
        escalate(db, incident, 0, 'Engineer', 'Immediate escalation required by matched rule', user)
    audit(db, user, report, 'CREATE')
    audit(db, user, incident, 'CREATE')
    refresh_machine(db, machine.id)
    return incident


def transition(db, user, incident_id, action, payload):
    incident = get_incident(db, user, incident_id, lock=True)
    old = record(incident)
    role = role_name(db, user)
    require_role(db, user, WORKERS)
    if role not in MANAGERS and incident.assigned_user_id not in {None, user.id}:
        raise HTTPException(403, 'Only the assignee or a supervisor can update this incident')
    transitions = {'acknowledge': ({'ASSIGNED', 'ESCALATED'}, 'ACKNOWLEDGED', 'acknowledged_at'),
                   'start': ({'ACKNOWLEDGED'}, 'IN_PROGRESS', 'started_at'),
                   'wait': ({'IN_PROGRESS'}, 'WAITING', None), 'resume': ({'WAITING'}, 'IN_PROGRESS', None),
                   'resolve': ({'IN_PROGRESS'}, 'RESOLVED', 'resolved_at'),
                   'verify': ({'RESOLVED'}, 'VERIFIED', 'verified_at'), 'close': ({'VERIFIED'}, 'CLOSED', 'closed_at')}
    if action in {'verify', 'close', 'reopen', 'assign', 'severity', 'escalate'}:
        require_role(db, user, MANAGERS)
    if action in {'resolve', 'reopen', 'escalate', 'severity', 'comment'} and len(payload.description.strip()) < 3:
        raise HTTPException(422, 'Enter a description or corrective action (at least 3 characters)')
    if action in transitions:
        allowed, target, timestamp = transitions[action]
        if incident.status not in allowed:
            raise HTTPException(409, f'Cannot {action} an incident in {incident.status}')
        incident.status = target
        if timestamp:
            setattr(incident, timestamp, utcnow())
        if action == 'resolve':
            notify(db, incident, 'RESOLUTION', payload.description)
            notify(db, incident, 'VERIFICATION_REQUIRED', payload.description, recipients(db, incident, MANAGERS))
    elif action == 'assign':
        if incident.status in TERMINAL:
            raise HTTPException(409, 'Reopen this incident before reassigning it')
        department_id = payload.assigned_department_id or incident.assigned_department_id
        if not db.get(Department, department_id):
            raise HTTPException(422, 'Department not found')
        if payload.assigned_user_id:
            target = db.get(User, payload.assigned_user_id)
            if not target or not target.is_active or target.factory_id != db.get(Report, incident.report_id).factory_id or target.department_id != department_id or role_name(db, target) not in WORKERS:
                raise HTTPException(422, 'Select an active worker in the same factory and target department')
        incident.assigned_department_id = department_id
        incident.assigned_user_id = payload.assigned_user_id
        if incident.status == 'OPEN':
            incident.status = 'ASSIGNED'
        notify(db, incident, 'ASSIGNMENT', payload.description or 'Assignment updated')
    elif action == 'reopen':
        if incident.status not in TERMINAL:
            raise HTTPException(409, 'Only resolved, verified or closed incidents can be reopened')
        incident.status = 'ASSIGNED'
        for field in ['acknowledged_at', 'started_at', 'resolved_at', 'verified_at', 'closed_at']:
            setattr(incident, field, None)
        policy = db.scalar(select(SLAPolicy).where(SLAPolicy.severity == incident.severity))
        incident.sla_due_at = utcnow() + timedelta(minutes=policy.minutes)
        notify(db, incident, 'ASSIGNMENT', 'Incident reopened: ' + payload.description)
    elif action == 'severity':
        if not payload.severity or incident.status in TERMINAL:
            raise HTTPException(409, 'Select a severity on an active incident')
        incident.severity = payload.severity
        policy = db.scalar(select(SLAPolicy).where(SLAPolicy.severity == incident.severity))
        incident.sla_due_at = incident.created_at + timedelta(minutes=policy.minutes)
    elif action == 'escalate':
        if incident.status in TERMINAL:
            raise HTTPException(409, 'Cannot escalate a resolved incident')
        levels = list(db.scalars(select(Escalation.level).where(Escalation.incident_id == incident.id)))
        escalate(db, incident, max(levels, default=0) + 1, 'Supervisor', payload.description, user)
        # Preserve work state; escalation is tracked separately to avoid disrupting the lifecycle.
    elif action == 'comment':
        db.add(Comment(incident_id=incident.id, user_id=user.id, comment=payload.description))
    else:
        raise HTTPException(404, 'Unknown incident action')
    timeline(db, incident, user, action.upper(), payload.description or action.replace('_', ' ').capitalize())
    refresh_machine(db, incident.machine_id)
    audit(db, user, incident, action.upper(), old)
    return incident
