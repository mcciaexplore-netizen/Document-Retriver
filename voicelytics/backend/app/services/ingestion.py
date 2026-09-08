from fastapi import HTTPException
from sqlalchemy import select
from app.models.entities import Machine, MachineLog
from app.repositories.access import get_machine
from app.rules.engine import evaluate
from app.schemas.payloads import ReportInput
from app.services.workflow import create_report, refresh_machine, audit


def ingest(db, user, payload, source='SYSTEM'):
    machine = db.scalar(select(Machine).where(Machine.machine_code == payload.machine_code))
    if not machine:
        raise HTTPException(422, f'Unknown machine {payload.machine_code}')
    get_machine(db, user, machine.id)
    if db.scalar(select(MachineLog.id).where(MachineLog.machine_id == machine.id, MachineLog.timestamp == payload.timestamp)):
        raise HTTPException(409, 'A log already exists for this machine and timestamp')
    values = payload.model_dump(exclude={'machine_code'})
    log = MachineLog(machine_id=machine.id, **values, raw_payload=payload.model_dump(mode='json'))
    db.add(log)
    db.flush()
    data = {**values, 'text': ''}
    result = evaluate(db, data, machine)
    incident = None
    if result['create_incident']:
        description = f'{source} log #{log.id} for {machine.machine_code}: ' + ', '.join(f'{k}={v}' for k, v in values.items() if v is not None)
        incident = create_report(db, user, ReportInput(machine_id=machine.id, input_type=source, description=description), data=data)
    refresh_machine(db, machine.id)
    audit(db, user, log, 'INGEST')
    return {'log_id': log.id, 'incident_id': incident.id if incident else None, 'evaluation': result}
