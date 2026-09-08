from datetime import timedelta
from sqlalchemy import select
from app.database.session import SessionLocal, utcnow
from app.models.entities import *
from app.core.config import settings
from app.core.security import hash_password
from app.schemas.payloads import ReportInput, ActionInput
from app.services.workflow import create_report, transition


def seed(db, password=None):
    if db.scalar(select(User.id).limit(1)):
        return
    password = password or settings.demo_password
    if not password or password.startswith('replace-with'):
        raise RuntimeError('Set DEMO_PASSWORD to a private password (10–72 bytes) before seeding')
    roles = ['Admin', 'Plant Manager', 'Supervisor', 'Engineer', 'Technician', 'Operator', 'Safety Officer', 'Quality Officer', 'Stores Manager']
    departments = ['Mechanical', 'Electrical', 'Safety', 'Stores', 'Quality', 'Production', 'Maintenance']
    for name in roles:
        db.add(Role(name=name, description=name + ' operations access'))
    for name in departments:
        db.add(Department(name=name))
    db.flush()
    role = {r.name: r.id for r in db.scalars(select(Role))}
    dept = {r.name: r.id for r in db.scalars(select(Department))}
    factory = Factory(name='Pune Manufacturing Plant', code='PUNE-01', location='Pune, Maharashtra')
    db.add(factory); db.flush()
    line = ProductionLine(factory_id=factory.id, name='Assembly Line A', code='LINE-A'); db.add(line); db.flush()
    stations = []
    for name in ['S', 'T', 'U']:
        station = Station(production_line_id=line.id, name='Station ' + name, code='ST-' + name); db.add(station); db.flush(); stations.append(station)
    for name, start, end in [('Morning', '06:00', '14:00'), ('Afternoon', '14:00', '22:00'), ('Night', '22:00', '06:00')]:
        db.add(Shift(factory_id=factory.id, name=name, start_time=start, end_time=end))
    machine_specs = [('#55-04', 'CNC Spindle', 0, True), ('#55-05', 'Hydraulic Press', 1, False), ('#55-06', 'Conveyor', 1, False), ('#55-07', 'Compressor', 2, False), ('#55-01', 'Machining Center', 0, True)]
    machines = []
    for code, name, station_index, critical in machine_specs:
        machine = Machine(station_id=stations[station_index].id, machine_code=code, machine_name=name, manufacturer='Pune Industrial Systems', model='Series 2024', serial_number='PUN-' + code.strip('#'), is_critical=critical)
        db.add(machine); db.flush(); machines.append(machine)
    specs = [('Admin', 'admin', 'Admin', 'Production'), ('Plant Manager', 'manager', 'Plant Manager', 'Production'), ('Supervisor Mehta', 'supervisor', 'Supervisor', 'Mechanical'),
             ('Engineer Ravi', 'ravi', 'Engineer', 'Mechanical'), ('Engineer Anita', 'anita', 'Engineer', 'Maintenance'), ('Technician A', 'technician', 'Technician', 'Mechanical'),
             ('Technician B', 'technicianb', 'Technician', 'Maintenance'), ('Operator', 'operator', 'Operator', 'Production'), ('Safety Officer', 'safety', 'Safety Officer', 'Safety'),
             ('Quality Officer', 'quality', 'Quality Officer', 'Quality'), ('Stores Manager', 'stores', 'Stores Manager', 'Stores')]
    users = {}
    hashed = hash_password(password)
    for index, (name, email, role_value, department) in enumerate(specs, 1):
        user = User(name=name, employee_id=f'EMP-{index:03d}', email=email + '@voicelytics.local', password_hash=hashed, role_id=role[role_value], department_id=dept[department], factory_id=factory.id)
        db.add(user); db.flush(); users[email] = user
    category_specs = [('Mechanical', 'Mechanical'), ('Electrical', 'Electrical'), ('Safety', 'Safety'), ('Inventory', 'Stores'), ('Quality', 'Quality'), ('Production', 'Production'), ('Maintenance', 'Maintenance'), ('Temperature', 'Maintenance'), ('Vibration', 'Mechanical'), ('Abnormal Noise', 'Mechanical'), ('Machine Breakdown', 'Maintenance')]
    for name, department in category_specs:
        db.add(IssueCategory(name=name, default_department=dept[department], default_severity='MEDIUM'))
    db.flush()
    categories = {c.name: c.id for c in db.scalars(select(IssueCategory))}
    synonyms = [('English', 'machine stopped'), ('Hindi', 'machine band hai'), ('Hindi', 'मशीन बंद है'), ('Marathi', 'machine band aahe'), ('Marathi', 'मशीन बंद आहे')]
    for language, keyword in synonyms:
        db.add(Keyword(language=language, keyword=keyword, normalized_keyword='machine stopped', event_code='MACHINE_STOPPED', category_id=categories['Machine Breakdown'], severity='HIGH'))
    for severity, minutes in [('CRITICAL', 15), ('HIGH', 30), ('MEDIUM', 120), ('WARNING', 120), ('LOW', 480)]:
        db.add(SLAPolicy(severity=severity, minutes=minutes))
        for level, delay, target in [(1, minutes, 'Supervisor'), (2, minutes * 2, 'Plant Manager'), (3, minutes * 4, 'Admin')]:
            db.add(EscalationRule(severity=severity, level=level, after_minutes=delay, target_role=target))
    def rule(name, condition, category, department, severity, priority, immediate=False):
        db.add(Rule(name=name, rule_type='TEXT' if condition['field'] == 'text' else 'EVENT' if condition['field'] in {'event_codes', 'status_code'} else 'THRESHOLD', priority=priority,
                    conditions_json={'any': [condition]}, actions_json={'category': category, 'department': department, 'severity': severity, 'priority': 1 if severity == 'CRITICAL' else 2 if severity == 'HIGH' else 3, 'escalation_required': immediate, 'create_incident': True, 'alerts': []}))
    rule('Immediate safety hazard', {'field': 'text', 'op': 'contains_any', 'value': ['fire', 'smoke', 'spark', 'injury', 'emergency']}, 'Safety', 'Safety', 'CRITICAL', 1, True)
    rule('Abnormal spindle and bearing noise', {'field': 'text', 'op': 'contains_any', 'value': ['noise', 'abnormal noise', 'bearing noise', 'spindle noise']}, 'Abnormal Noise', 'Mechanical', 'MEDIUM', 10)
    rule('Machine stopped dictionary event', {'field': 'event_codes', 'op': 'contains_any', 'value': ['MACHINE_STOPPED']}, 'Machine Breakdown', 'Maintenance', 'HIGH', 15)
    rule('Stopped machine status', {'field': 'status_code', 'op': 'eq', 'value': 'STOPPED'}, 'Machine Breakdown', 'Maintenance', 'HIGH', 16)
    for field, category, department in [('temperature', 'Temperature', 'Maintenance'), ('vibration', 'Vibration', 'Mechanical')]:
        for level, severity, priority in [('critical', 'CRITICAL', 2), ('warning', 'WARNING', 20)]:
            rule(f'{level.capitalize()} {field}', {'field': field, 'op': 'gte', 'value': f'machine.{level}_{field}'}, category, department, severity, priority, level == 'critical')
    rule('Bearing inventory reorder threshold', {'field': 'stock_level', 'op': 'lte', 'value': 'machine.reorder_level'}, 'Inventory', 'Stores', 'MEDIUM', 30)
    db.flush()
    reports = [(0, 'Machine #55-04 has abnormal spindle noise.', 'technician'), (1, 'Oil pressure inspection requested on hydraulic press.', 'technicianb'), (2, 'Smoke near the conveyor motor. Safety inspection required.', 'operator'), (3, 'machine band aahe', 'technicianb'), (4, 'Scheduled coolant inspection complete; follow-up required.', 'anita')]
    for index, (machine_index, description, reporter) in enumerate(reports):
        incident = create_report(db, users[reporter], ReportInput(machine_id=machines[machine_index].id, description=description))
        if index == 4:
            for action in ['acknowledge', 'start', 'resolve', 'verify', 'close']:
                transition(db, users['supervisor'], incident.id, action, ActionInput(description='Coolant checked, filter replaced and operating cycle verified.'))
    for index, machine in enumerate(machines):
        db.add(MachineLog(machine_id=machine.id, timestamp=utcnow() - timedelta(minutes=index + 1), temperature=62 + index * 3, vibration=2.3 + index * .4, pressure=5.1, runtime=240, production_count=120 + index * 5, stock_level=24, status_code='RUNNING', raw_payload={'source': 'demo seed'}))
    db.commit()


if __name__ == '__main__':
    with SessionLocal() as session:
        seed(session)
    print('Demo seed ready. Existing records are preserved.')
