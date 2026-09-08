from fastapi import HTTPException
from sqlalchemy import select, or_
from app.models.entities import Machine, Station, ProductionLine, Incident, Report
from app.core.security import role_name, MANAGERS


def machine_factory(db, machine):
    station = db.get(Station, machine.station_id)
    line = db.get(ProductionLine, station.production_line_id)
    return line.factory_id


def check_factory(db, user, factory_id):
    if role_name(db, user) != 'Admin' and user.factory_id != factory_id:
        raise HTTPException(404, 'Record not found')


def get_machine(db, user, machine_id):
    machine = db.get(Machine, machine_id)
    if not machine:
        raise HTTPException(404, 'Machine not found')
    check_factory(db, user, machine_factory(db, machine))
    return machine


def incident_query(db, user):
    query = select(Incident).join(Report, Incident.report_id == Report.id)
    role = role_name(db, user)
    if role != 'Admin':
        query = query.where(Report.factory_id == user.factory_id)
    if role not in MANAGERS:
        query = query.where(or_(Incident.assigned_department_id == user.department_id,
                                Incident.assigned_user_id == user.id, Report.reporter_id == user.id))
    return query


def get_incident(db, user, incident_id, lock=False):
    query = incident_query(db, user).where(Incident.id == incident_id)
    if lock:
        query = query.with_for_update(of=Incident)
    incident = db.scalar(query)
    if not incident:
        raise HTTPException(404, 'Incident not found')
    return incident


def get_report(db, user, report_id):
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(404, 'Report not found')
    check_factory(db, user, report.factory_id)
    if report.reporter_id != user.id and not db.scalar(incident_query(db, user).where(Incident.report_id == report_id)):
        raise HTTPException(404, 'Report not found')
    return report
