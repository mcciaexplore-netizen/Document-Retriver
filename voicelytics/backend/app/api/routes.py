import csv
import io
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, Header, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import ValidationError, create_model, ConfigDict
from sqlalchemy import select, or_, func, String, Integer, Float, Boolean
from app.database.session import get_db, utcnow, SessionLocal
from app.models.entities import *
from app.schemas.payloads import Login, ReportInput, ActionInput, RuleInput, RuleTest, LogInput, UserInput
from app.core.security import current_user, role_name, require_role, verify_password, hash_password, token_for, key_user, MANAGERS
from app.repositories.access import get_machine, get_incident, get_report, check_factory, machine_factory, incident_query
from app.services.workflow import create_report, transition, audit, TERMINAL
from app.services.ingestion import ingest
from app.services.storage import storage, ALLOWED
from app.services.notifications import deliver_email
from app.rules.engine import evaluate
from app.websocket.manager import manager
from app.utils.serialization import record

router = APIRouter(prefix='/api')


def public_user(db, user):
    return {**record(user), 'role': role_name(db, user)}


def mail_after_commit(ids):
    with SessionLocal() as db:
        deliver_email(db, ids)


async def commit(db, background=None):
    pending = [n for n in db.new if isinstance(n, Notification)]
    db.flush()
    ids = [n.id for n in pending]
    db.commit()
    await manager.publish()
    if background and ids:
        background.add_task(mail_after_commit, ids)


@router.post('/auth/login')
def login(payload: Login, db=Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, 'Email or password is incorrect')
    return {'access_token': token_for(user), 'token_type': 'bearer', 'user': public_user(db, user)}


@router.get('/auth/me')
def me(user=Depends(current_user), db=Depends(get_db)):
    return public_user(db, user)


@router.post('/auth/ws-ticket')
def ws_ticket(user=Depends(current_user)):
    return {'ticket': token_for(user, purpose='websocket', minutes=1)}


CONFIG = {'factories': Factory, 'production-lines': ProductionLine, 'stations': Station, 'machines': Machine,
          'shifts': Shift, 'departments': Department, 'roles': Role, 'categories': IssueCategory,
          'keyword-dictionary': Keyword, 'sla-policies': SLAPolicy, 'escalation-rules': EscalationRule}


def config_records(db, user, kind):
    model = CONFIG[kind]
    rows = list(db.scalars(select(model).order_by(model.id)))
    if role_name(db, user) != 'Admin':
        if kind == 'factories':
            rows = [r for r in rows if r.id == user.factory_id]
        elif kind in {'production-lines', 'shifts'}:
            rows = [r for r in rows if r.factory_id == user.factory_id]
        elif kind == 'stations':
            rows = [r for r in rows if db.get(ProductionLine, r.production_line_id).factory_id == user.factory_id]
        elif kind == 'machines':
            rows = [r for r in rows if machine_factory(db, r) == user.factory_id]
    return [record(r) for r in rows]


@router.get('/lookup')
def lookup(user=Depends(current_user), db=Depends(get_db)):
    result = {kind: config_records(db, user, kind) for kind in CONFIG}
    query = select(User).where(User.is_active.is_(True))
    if role_name(db, user) != 'Admin':
        query = query.where(User.factory_id == user.factory_id)
    result['employees'] = [{'id': u.id, 'name': u.name, 'role': role_name(db, u), 'department_id': u.department_id, 'factory_id': u.factory_id} for u in db.scalars(query)]
    return result


def validate_config(db, model, payload, existing=None):
    fields = {}
    for c in model.__table__.columns:
        if c.name in {'id', 'created_at'}:
            continue
        typ = bool if isinstance(c.type, Boolean) else int if isinstance(c.type, Integer) else float if isinstance(c.type, Float) else str
        default = getattr(existing, c.name) if existing else c.default.arg if c.default is not None and c.default.is_scalar else None if c.nullable else ...
        fields[c.name] = (typ | None if c.nullable else typ, default)
    schema = create_model('Configuration', __config__=ConfigDict(extra='forbid', str_strip_whitespace=True, allow_inf_nan=False), **fields)
    try:
        values = schema.model_validate(payload).model_dump()
    except ValidationError as exc:
        raise HTTPException(422, str(exc))
    for name, value in values.items():
        col = model.__table__.columns[name]
        if isinstance(value, str) and (not value and not col.nullable and name not in {'description', 'manufacturer', 'model', 'serial_number', 'location'} or len(value) > (getattr(col.type, 'length', None) or 2000)):
            raise HTTPException(422, f'Invalid {name}')
        for fk in col.foreign_keys:
            target = next(m for m in Base.registry.mappers if m.local_table.name == fk.column.table.name).class_
            if value is not None and not db.get(target, value):
                raise HTTPException(422, f'Invalid {name}')
    if model is Machine and (values['warning_temperature'] >= values['critical_temperature'] or values['warning_vibration'] >= values['critical_vibration'] or values['warning_vibration'] < 0 or values['reorder_level'] < 0):
        raise HTTPException(422, 'Warning thresholds must be below critical thresholds; vibration and reorder levels cannot be negative')
    if 'severity' in values and values['severity'] not in {'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'WARNING'}:
        raise HTTPException(422, 'Invalid severity')
    if model is SLAPolicy and values['minutes'] <= 0:
        raise HTTPException(422, 'SLA minutes must be positive')
    if model is EscalationRule and (values['level'] < 0 or values['after_minutes'] < 0 or not db.scalar(select(Role).where(Role.name == values['target_role']))):
        raise HTTPException(422, 'Invalid escalation level, delay or target role')
    if model is Shift:
        try:
            datetime.strptime(values['start_time'], '%H:%M'); datetime.strptime(values['end_time'], '%H:%M')
        except ValueError:
            raise HTTPException(422, 'Shift times must use HH:MM')
    if model is Keyword and values['language'] not in {'English', 'Hindi', 'Marathi'}:
        raise HTTPException(422, 'Unsupported language')
    return values


def install_config_routes(kind, model):
    async def listing(user=Depends(current_user), db=Depends(get_db)):
        return config_records(db, user, kind)

    async def create(payload: dict, request: Request, user=Depends(current_user), db=Depends(get_db)):
        require_role(db, user, {'Admin'})
        entity = model(**validate_config(db, model, payload))
        db.add(entity); db.flush()
        audit(db, user, entity, 'CREATE', ip=request.client.host)
        await commit(db)
        return record(entity)

    async def update(entity_id: int, payload: dict, request: Request, user=Depends(current_user), db=Depends(get_db)):
        require_role(db, user, {'Admin'})
        entity = db.get(model, entity_id)
        if not entity:
            raise HTTPException(404, 'Record not found')
        if model is Role and 'name' in payload and payload['name'] != entity.name:
            raise HTTPException(422, 'Built-in role names define permissions and cannot be renamed')
        old = record(entity)
        for key, value in validate_config(db, model, payload, entity).items():
            setattr(entity, key, value)
        audit(db, user, entity, 'UPDATE', old, request.client.host)
        await commit(db)
        return record(entity)

    router.add_api_route('/' + kind, listing, methods=['GET'], name='list_' + kind)
    router.add_api_route('/' + kind, create, methods=['POST'], name='create_' + kind)
    router.add_api_route('/' + kind + '/{entity_id}', update, methods=['PUT'], name='update_' + kind)


for config_kind, config_model in CONFIG.items():
    install_config_routes(config_kind, config_model)


def incident_view(db, incident):
    report = db.get(Report, incident.report_id)
    machine = db.get(Machine, incident.machine_id)
    return {**record(incident), 'description': report.description, 'factory_id': report.factory_id, 'production_line_id': report.production_line_id,
            'station_id': report.station_id, 'reporter_id': report.reporter_id, 'machine_name': machine.machine_name,
            'machine_code': machine.machine_code, 'category': db.get(IssueCategory, incident.category_id).name,
            'department': db.get(Department, incident.assigned_department_id).name,
            'assigned_user': db.get(User, incident.assigned_user_id).name if incident.assigned_user_id else 'Department queue',
            'reporter': db.get(User, report.reporter_id).name}


def filtered_incidents(db, user, params):
    query = incident_query(db, user)
    for key, column in {'factory_id': Report.factory_id, 'production_line_id': Report.production_line_id, 'station_id': Report.station_id,
                        'machine_id': Incident.machine_id, 'category_id': Incident.category_id, 'department_id': Incident.assigned_department_id,
                        'employee_id': Report.reporter_id, 'severity': Incident.severity, 'status': Incident.status}.items():
        if params.get(key):
            query = query.where(column == params[key])
    for key, op in [('date_from', 'ge'), ('date_to', 'le')]:
        if params.get(key):
            try:
                value = datetime.fromisoformat(params[key].replace('Z', '+00:00'))
                value = value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
                if key == 'date_to' and len(params[key]) == 10:
                    value += timedelta(days=1, microseconds=-1)
            except ValueError:
                raise HTTPException(422, 'Invalid date filter')
            query = query.where(Incident.created_at >= value if op == 'ge' else Incident.created_at <= value)
    if params.get('q'):
        needle = '%' + params['q'] + '%'
        query = query.where(or_(Incident.incident_number.ilike(needle), Report.description.ilike(needle)))
    if params.get('open') == 'true':
        query = query.where(Incident.status.not_in(TERMINAL))
    if params.get('overdue') == 'true':
        query = query.where(Incident.status.not_in(TERMINAL), Incident.sla_due_at < utcnow())
    if params.get('pending') == 'true':
        query = query.where(Incident.status.in_(['OPEN', 'ASSIGNED', 'ESCALATED']))
    if params.get('resolved_today') == 'true':
        query = query.where(Incident.resolved_at >= utcnow().replace(hour=0, minute=0, second=0, microsecond=0))
    if params.get('resolved') == 'true':
        query = query.where(Incident.resolved_at.is_not(None))
    if params.get('machine_status'):
        query = query.join(Machine, Machine.id == Incident.machine_id).where(Machine.status == params['machine_status'])
    return list(db.scalars(query.order_by(Incident.created_at.desc(), Incident.id.desc())))


@router.get('/incidents')
def incidents(request: Request, user=Depends(current_user), db=Depends(get_db)):
    return [incident_view(db, i) for i in filtered_incidents(db, user, request.query_params)]


@router.post('/reports')
async def report_create(payload: ReportInput, background: BackgroundTasks, user=Depends(current_user), db=Depends(get_db)):
    incident = create_report(db, user, payload)
    await commit(db, background)
    return incident_view(db, incident)


@router.get('/reports/export')
def export(request: Request, user=Depends(current_user), db=Depends(get_db)):
    rows = [incident_view(db, i) for i in filtered_incidents(db, user, request.query_params)]
    stream = io.StringIO()
    columns = ['incident_number', 'machine_code', 'description', 'category', 'severity', 'status', 'department', 'assigned_user', 'created_at', 'sla_due_at', 'resolved_at']
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
    writer.writeheader()
    for row in rows:
        # Prevent spreadsheet formulas from executing when exported text is opened.
        writer.writerow({k: "'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else v for k, v in row.items()})
    return StreamingResponse(iter([stream.getvalue()]), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename=voicelytics-incidents.csv'})


@router.get('/reports/{report_id}')
def report_get(report_id: int, user=Depends(current_user), db=Depends(get_db)):
    return record(get_report(db, user, report_id))


@router.get('/incidents/{incident_id}')
def incident_detail(incident_id: int, user=Depends(current_user), db=Depends(get_db)):
    incident = get_incident(db, user, incident_id)
    result = incident_view(db, incident)
    result['report'] = record(db.get(Report, incident.report_id))
    for key, model, column, value in [('timeline', IncidentAction, IncidentAction.incident_id, incident.id), ('comments', Comment, Comment.incident_id, incident.id),
                                      ('escalations', Escalation, Escalation.incident_id, incident.id), ('audio', AudioFile, AudioFile.report_id, incident.report_id), ('attachments', Attachment, Attachment.report_id, incident.report_id)]:
        result[key] = [record(r) for r in db.scalars(select(model).where(column == value).order_by(model.id))]
    return result


@router.post('/incidents/{incident_id}/{action}')
async def incident_action(incident_id: int, action: str, payload: ActionInput, background: BackgroundTasks, user=Depends(current_user), db=Depends(get_db)):
    result = transition(db, user, incident_id, action, payload)
    await commit(db, background)
    return incident_view(db, result)


async def add_evidence(report_id, file, audio, user, db, duration=None):
    report = get_report(db, user, report_id)
    if report.reporter_id != user.id and role_name(db, user) not in MANAGERS:
        raise HTTPException(403, 'Only the reporter or a supervisor may attach evidence')
    key, mime = await storage.save(file, audio)
    if audio:
        entity = AudioFile(report_id=report_id, file_path=key, original_filename=Path(file.filename).name, mime_type=mime, duration=duration)
    else:
        entity = Attachment(report_id=report_id, file_path=key, filename=Path(file.filename).name, file_type=mime, uploaded_by=user.id)
    try:
        db.add(entity); db.flush(); audit(db, user, entity, 'UPLOAD')
        await commit(db)
    except Exception:
        storage.path(key).unlink(missing_ok=True)
        raise
    return record(entity)


@router.post('/reports/{report_id}/audio')
async def audio_upload(report_id: int, file: UploadFile = File(...), duration: float = Form(0, ge=0, le=86400), user=Depends(current_user), db=Depends(get_db)):
    return await add_evidence(report_id, file, True, user, db, duration)


@router.post('/reports/{report_id}/attachments')
async def attachment_upload(report_id: int, file: UploadFile = File(...), user=Depends(current_user), db=Depends(get_db)):
    return await add_evidence(report_id, file, False, user, db)


@router.get('/files/{kind}/{file_id}')
def file_download(kind: str, file_id: int, user=Depends(current_user), db=Depends(get_db)):
    model = {'audio': AudioFile, 'attachments': Attachment, 'documents': MaintenanceDocument}.get(kind)
    entity = db.get(model, file_id) if model else None
    if not entity:
        raise HTTPException(404, 'File not found')
    if kind == 'documents':
        get_machine(db, user, entity.machine_id)
    else:
        get_report(db, user, entity.report_id)
    path = storage.path(entity.file_path)
    if not path.is_file():
        raise HTTPException(404, 'File is unavailable')
    return FileResponse(path, filename=entity.original_filename if kind == 'audio' else entity.filename,
                        media_type=ALLOWED.get(path.suffix, 'application/octet-stream'), headers={'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'private, no-store'})


@router.get('/machines/{machine_id}')
def machine_detail(machine_id: int, user=Depends(current_user), db=Depends(get_db)):
    machine = get_machine(db, user, machine_id)
    return {**record(machine), 'incidents': [incident_view(db, i) for i in db.scalars(incident_query(db, user).where(Incident.machine_id == machine_id).order_by(Incident.created_at.desc()))],
            'logs': [record(r) for r in db.scalars(select(MachineLog).where(MachineLog.machine_id == machine_id).order_by(MachineLog.timestamp.desc()).limit(100))],
            'documents': [record(r) for r in db.scalars(select(MaintenanceDocument).where(MaintenanceDocument.machine_id == machine_id))]}


@router.get('/rules')
def rules(user=Depends(current_user), db=Depends(get_db)):
    return [record(r) for r in db.scalars(select(Rule).order_by(Rule.priority, Rule.id))]


def check_rule_targets(db, payload):
    if not db.scalar(select(IssueCategory).where(IssueCategory.name == payload.actions_json.category, IssueCategory.active.is_(True))) or not db.scalar(select(Department).where(Department.name == payload.actions_json.department)):
        raise HTTPException(422, 'Select an existing active category and department')


@router.post('/rules/test')
def rule_test(payload: RuleTest, user=Depends(current_user), db=Depends(get_db)):
    require_role(db, user, {'Admin'})
    machine = get_machine(db, user, payload.machine_id)
    draft = [Rule(id=0, **payload.rule.model_dump())] if payload.rule else None
    return evaluate(db, payload.model_dump(exclude={'rule', 'machine_id'}), machine, draft)


@router.post('/rules')
async def rule_create(payload: RuleInput, user=Depends(current_user), db=Depends(get_db)):
    require_role(db, user, {'Admin'}); check_rule_targets(db, payload)
    rule = Rule(**payload.model_dump()); db.add(rule); db.flush()
    audit(db, user, rule, 'CREATE'); await commit(db)
    return record(rule)


@router.put('/rules/{rule_id}')
async def rule_update(rule_id: int, payload: RuleInput, user=Depends(current_user), db=Depends(get_db)):
    require_role(db, user, {'Admin'}); check_rule_targets(db, payload)
    rule = db.get(Rule, rule_id)
    if not rule:
        raise HTTPException(404, 'Rule not found')
    old = record(rule)
    for key, value in payload.model_dump().items():
        setattr(rule, key, value)
    audit(db, user, rule, 'UPDATE', old); await commit(db)
    return record(rule)


@router.delete('/rules/{rule_id}')
async def rule_delete(rule_id: int, user=Depends(current_user), db=Depends(get_db)):
    require_role(db, user, {'Admin'})
    rule = db.get(Rule, rule_id)
    if not rule:
        raise HTTPException(404, 'Rule not found')
    audit(db, user, rule, 'DELETE', record(rule)); db.delete(rule); await commit(db)
    return {'deleted': rule_id}


@router.post('/machine-logs')
async def log_create(payload: LogInput, background: BackgroundTasks, user=Depends(current_user), db=Depends(get_db)):
    result = ingest(db, user, payload); await commit(db, background)
    return result


@router.post('/v1/machine-logs')
async def external_log(payload: LogInput, background: BackgroundTasks, x_api_key: str = Header(...), db=Depends(get_db)):
    result = ingest(db, key_user(x_api_key, db), payload); await commit(db, background)
    return result


@router.get('/machine-logs')
def log_list(machine_id: int | None = None, user=Depends(current_user), db=Depends(get_db)):
    ids = [r['id'] for r in config_records(db, user, 'machines')]
    query = select(MachineLog).where(MachineLog.machine_id.in_(ids))
    if machine_id:
        query = query.where(MachineLog.machine_id == machine_id)
    return [record(r) for r in db.scalars(query.order_by(MachineLog.timestamp.desc()).limit(500))]


@router.post('/machine-logs/import')
async def csv_import(background: BackgroundTasks, file: UploadFile = File(...), user=Depends(current_user), db=Depends(get_db)):
    if not (file.filename or '').lower().endswith('.csv'):
        raise HTTPException(422, 'Select a CSV file')
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, 'CSV limit is 5 MB')
    try:
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error):
        raise HTTPException(422, 'CSV must be valid UTF-8')
    if not rows or len(rows) > 5000:
        raise HTTPException(422, 'CSV must contain 1–5000 data rows')
    errors, parsed, seen = [], [], set()
    for number, row in enumerate(rows, 2):
        try:
            payload = LogInput.model_validate({k: v for k, v in row.items() if v != ''})
            machine = db.scalar(select(Machine).where(Machine.machine_code == payload.machine_code))
            if not machine:
                raise ValueError('Unknown machine code')
            get_machine(db, user, machine.id)
            key = (machine.id, payload.timestamp)
            if key in seen or db.scalar(select(MachineLog.id).where(MachineLog.machine_id == machine.id, MachineLog.timestamp == payload.timestamp)):
                raise ValueError('Duplicate machine/timestamp')
            seen.add(key); parsed.append(payload)
        except (ValidationError, ValueError, HTTPException) as exc:
            errors.append({'row': number, 'message': exc.detail if isinstance(exc, HTTPException) else str(exc)})
    if errors:
        raise HTTPException(422, {'message': 'No rows imported. Correct these rows and retry.', 'errors': errors})
    result = [ingest(db, user, payload, 'CSV') for payload in parsed]
    await commit(db, background)
    return {'imported': len(result), 'results': result}


@router.get('/documents')
def documents(q: str = '', machine_id: int | None = None, document_type: str = '', user=Depends(current_user), db=Depends(get_db)):
    ids = [r['id'] for r in config_records(db, user, 'machines')]
    query = select(MaintenanceDocument).where(MaintenanceDocument.machine_id.in_(ids))
    if machine_id:
        query = query.where(MaintenanceDocument.machine_id == machine_id)
    if document_type:
        query = query.where(MaintenanceDocument.document_type == document_type)
    if q:
        query = query.where(or_(MaintenanceDocument.title.ilike('%' + q + '%'), MaintenanceDocument.tags.ilike('%' + q + '%'), MaintenanceDocument.filename.ilike('%' + q + '%')))
    return [record(d) for d in db.scalars(query.order_by(MaintenanceDocument.created_at.desc()))]


@router.post('/documents')
async def document_upload(file: UploadFile = File(...), machine_id: int = Form(...), title: str = Form(..., min_length=1, max_length=200),
                          document_type: str = Form('Manual', max_length=60), tags: str = Form('', max_length=500), revision: str = Form('1', max_length=40), user=Depends(current_user), db=Depends(get_db)):
    get_machine(db, user, machine_id)
    key, _ = await storage.save(file)
    entity = MaintenanceDocument(machine_id=machine_id, title=title, document_type=document_type, filename=Path(file.filename).name, file_path=key, tags=tags, revision=revision, uploaded_by=user.id)
    try:
        db.add(entity); db.flush(); audit(db, user, entity, 'UPLOAD'); await commit(db)
    except Exception:
        storage.path(key).unlink(missing_ok=True)
        raise
    return record(entity)


@router.get('/notifications')
def notifications(user=Depends(current_user), db=Depends(get_db)):
    allowed = incident_query(db, user).with_only_columns(Incident.id)
    return [record(n) for n in db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.incident_id.in_(allowed)).order_by(Notification.created_at.desc()).limit(300))]


@router.post('/notifications/{notification_id}/read')
async def notification_read(notification_id: int, user=Depends(current_user), db=Depends(get_db)):
    notification = db.get(Notification, notification_id)
    if not notification or notification.user_id != user.id:
        raise HTTPException(404, 'Notification not found')
    notification.read = True; await commit(db)
    return record(notification)


def summary_data(db, user, params):
    rows = filtered_incidents(db, user, params)
    machines = config_records(db, user, 'machines')
    if params.get('factory_id'):
        machines = [m for m in machines if str(machine_factory(db, db.get(Machine, m['id']))) == params['factory_id']]
    active = [i for i in rows if i.status not in TERMINAL]
    resolved = [i for i in rows if i.resolved_at]
    acknowledged = [i for i in rows if i.acknowledged_at]
    now = utcnow()
    avg = lambda values: round(sum(values) / len(values), 1) if values else 0
    groups = lambda values: [{'name': name, 'value': count} for name, count in Counter(values).items()]
    return {'metrics': {'total_incidents': len(rows), 'open_incidents': len(active), 'critical_incidents': sum(i.severity == 'CRITICAL' for i in active),
                        'machines_down': sum(m['status'] in {'CRITICAL', 'OFFLINE'} for m in machines), 'machines_warning': sum(m['status'] == 'WARNING' for m in machines),
                        'pending_acknowledgement': sum(i.acknowledged_at is None for i in active), 'overdue_sla': sum(i.sla_due_at < now for i in active),
                        'resolved_today': sum(i.resolved_at.date() == now.date() for i in resolved), 'resolved_incidents': len(resolved),
                        'average_resolution_minutes': avg([(i.resolved_at - i.created_at).total_seconds() / 60 for i in resolved]),
                        'average_acknowledgement_minutes': avg([(i.acknowledged_at - i.created_at).total_seconds() / 60 for i in acknowledged]),
                        'sla_compliance': round(100 * sum(i.resolved_at <= i.sla_due_at for i in resolved) / len(resolved), 1) if resolved else None,
                        'repeated_incidents': sum(n - 1 for n in Counter((i.machine_id, i.category_id) for i in rows).values() if n > 1),
                        'machine_downtime_minutes': downtime_minutes(db, rows, now)},
            'category': groups(db.get(IssueCategory, i.category_id).name for i in rows), 'severity': groups(i.severity for i in rows),
            'trend': sorted(groups(i.created_at.strftime('%Y-%m-%d') for i in rows), key=lambda r: r['name']), 'machine_status': groups(m['status'] for m in machines),
            'production_line': groups(db.get(ProductionLine, db.get(Report, i.report_id).production_line_id).name for i in rows),
            'problem_machines': groups(db.get(Machine, i.machine_id).machine_code for i in rows),
            'resolution': [{'name': severity, 'value': avg([(i.resolved_at - i.created_at).total_seconds() / 60 for i in resolved if i.severity == severity])} for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']],
            'recent_incidents': [incident_view(db, i) for i in rows[:8]], 'critical_alerts': [incident_view(db, i) for i in active if i.severity == 'CRITICAL'], 'machines': machines}


def downtime_minutes(db, incidents, now):
    # Incident-derived downtime estimate: merge overlapping breakdown windows per machine.
    windows = {}
    for i in incidents:
        if db.get(IssueCategory, i.category_id).name == 'Machine Breakdown':
            windows.setdefault(i.machine_id, []).append((i.created_at, i.resolved_at or now))
    total = 0
    for intervals in windows.values():
        start = end = None
        for a, b in sorted(intervals):
            if end is not None and a > end:
                total += (end - start).total_seconds(); start = end = None
            start = a if start is None else start
            end = max(end or b, b)
        if end:
            total += (end - start).total_seconds()
    return round(total / 60, 1)


@router.get('/dashboard/summary')
@router.get('/dashboard/incidents')
@router.get('/dashboard/machines')
@router.get('/analytics')
def dashboard(request: Request, user=Depends(current_user), db=Depends(get_db)):
    return summary_data(db, user, request.query_params)


@router.get('/operations-query')
def operations_query(template: str, machine_id: int, user=Depends(current_user), db=Depends(get_db)):
    machine = get_machine(db, user, machine_id)
    templates = {'machine-status', 'open-incidents', 'critical-incidents', 'today-incidents', 'maintenance-history', 'unresolved-incidents', 'assigned-engineer', 'sla-status', 'recent-logs'}
    if template not in templates:
        raise HTTPException(422, 'Select a supported query template')
    if template == 'machine-status':
        return [{'text': f'{machine.machine_code}: {machine.status}', 'source': 'machines', 'record_id': machine.id, 'href': f'/machines/{machine.id}', 'timestamp': machine.created_at}]
    if template == 'recent-logs':
        return [{'text': f'Temperature {r.temperature}; vibration {r.vibration}; status {r.status_code}', 'source': 'machine_logs', 'record_id': r.id, 'timestamp': r.timestamp, 'href': f'/logs?machine_id={machine.id}&record_id={r.id}'} for r in db.scalars(select(MachineLog).where(MachineLog.machine_id == machine_id).order_by(MachineLog.timestamp.desc()).limit(10))]
    params = {'machine_id': machine_id}
    if template in {'open-incidents', 'unresolved-incidents', 'assigned-engineer', 'sla-status'}:
        params['open'] = 'true'
    if template == 'critical-incidents':
        params.update(severity='CRITICAL', open='true')
    if template == 'today-incidents':
        params['date_from'] = utcnow().date().isoformat()
    rows = filtered_incidents(db, user, params)
    if template == 'maintenance-history':
        rows = [i for i in rows if i.resolved_at]
    return [{'text': f'{i.incident_number}: {i.status}; assigned to {db.get(User, i.assigned_user_id).name if i.assigned_user_id else "department queue"}; SLA {i.sla_due_at.isoformat()} UTC',
             'source': 'incidents', 'record_id': i.id, 'timestamp': i.created_at, 'href': f'/incidents/{i.id}'} for i in rows[:30]]


@router.get('/users')
def users(user=Depends(current_user), db=Depends(get_db)):
    require_role(db, user, {'Admin'})
    return [public_user(db, u) for u in db.scalars(select(User).order_by(User.id))]


async def save_user(payload, user, db, entity=None):
    require_role(db, user, {'Admin'})
    for model, field in [(Role, 'role_id'), (Department, 'department_id'), (Factory, 'factory_id')]:
        if not db.get(model, getattr(payload, field)):
            raise HTTPException(422, f'Invalid {field}')
    if entity and entity.id == user.id and (not payload.is_active or payload.role_id != user.role_id):
        raise HTTPException(409, 'You cannot deactivate or demote your own account')
    old = record(entity)
    values = payload.model_dump(exclude={'password'})
    values['email'] = values['email'].lower()
    if payload.password:
        values['password_hash'] = hash_password(payload.password)
    if not entity:
        if not payload.password:
            raise HTTPException(422, 'A password is required for new users')
        entity = User(**values); db.add(entity)
    else:
        for key, value in values.items():
            setattr(entity, key, value)
    db.flush(); audit(db, user, entity, 'UPDATE' if old else 'CREATE', old); await commit(db)
    return public_user(db, entity)


@router.post('/users')
async def user_create(payload: UserInput, user=Depends(current_user), db=Depends(get_db)):
    return await save_user(payload, user, db)


@router.put('/users/{user_id}')
async def user_update(user_id: int, payload: UserInput, user=Depends(current_user), db=Depends(get_db)):
    require_role(db, user, {'Admin'})
    entity = db.get(User, user_id)
    if not entity:
        raise HTTPException(404, 'User not found')
    return await save_user(payload, user, db, entity)


@router.get('/audit-logs')
def audit_logs(user=Depends(current_user), db=Depends(get_db)):
    require_role(db, user, {'Admin'})
    return [record(r) for r in db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(1000))]


@router.get('/api-keys')
def api_keys(user=Depends(current_user), db=Depends(get_db)):
    require_role(db, user, {'Admin'})
    return [record(r) for r in db.scalars(select(APIKey))]


@router.post('/api-keys')
async def api_key_create(payload: dict, user=Depends(current_user), db=Depends(get_db)):
    require_role(db, user, {'Admin'})
    name = str(payload.get('name', '')).strip()
    owner = db.get(User, payload.get('user_id', user.id))
    if not name or len(name) > 100 or not owner or not owner.is_active or role_name(db, owner) == 'Admin':
        raise HTTPException(422, 'Provide a name and an active non-admin account to scope this integration to one factory')
    key = secrets.token_urlsafe(32)
    entity = APIKey(name=name, user_id=owner.id, key_hash=hashlib.sha256(key.encode()).hexdigest())
    db.add(entity); db.flush(); audit(db, user, entity, 'CREATE'); await commit(db)
    return {**record(entity), 'key': key}


@router.delete('/api-keys/{key_id}')
async def api_key_revoke(key_id: int, user=Depends(current_user), db=Depends(get_db)):
    require_role(db, user, {'Admin'})
    entity = db.get(APIKey, key_id)
    if not entity:
        raise HTTPException(404, 'Key not found')
    old = record(entity); entity.active = False; audit(db, user, entity, 'REVOKE', old); await commit(db)
    return record(entity)


@router.get('/notification-settings')
def notification_settings(user=Depends(current_user), db=Depends(get_db)):
    entity = db.scalar(select(NotificationSetting).where(NotificationSetting.user_id == user.id))
    from app.core.config import settings
    return {'email_enabled': entity.email_enabled if entity else False, 'smtp_configured': bool(settings.smtp_host)}


@router.put('/notification-settings')
async def notification_settings_update(payload: dict, user=Depends(current_user), db=Depends(get_db)):
    if not isinstance(payload.get('email_enabled'), bool):
        raise HTTPException(422, 'email_enabled must be true or false')
    entity = db.scalar(select(NotificationSetting).where(NotificationSetting.user_id == user.id))
    if not entity:
        entity = NotificationSetting(user_id=user.id); db.add(entity); db.flush()
    old = record(entity); entity.email_enabled = payload['email_enabled']; audit(db, user, entity, 'UPDATE', old); await commit(db)
    return record(entity)
