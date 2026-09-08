from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey, JSON, UniqueConstraint
from app.database.session import Base, utcnow


class Identity:
    id = Column(Integer, primary_key=True)


class Created:
    created_at = Column(DateTime, default=utcnow, nullable=False)


class Role(Identity, Base):
    __tablename__ = 'roles'
    name = Column(String(80), unique=True, nullable=False)
    description = Column(Text, default='')


class Department(Identity, Base):
    __tablename__ = 'departments'
    name = Column(String(80), unique=True, nullable=False)


class Factory(Identity, Base):
    __tablename__ = 'factories'
    name = Column(String(150), nullable=False)
    code = Column(String(40), unique=True, nullable=False)
    location = Column(String(200), default='')
    status = Column(String(30), default='ACTIVE')


class ProductionLine(Identity, Base):
    __tablename__ = 'production_lines'
    factory_id = Column(ForeignKey('factories.id'), nullable=False)
    name = Column(String(150), nullable=False)
    code = Column(String(40), unique=True, nullable=False)


class Station(Identity, Base):
    __tablename__ = 'stations'
    production_line_id = Column(ForeignKey('production_lines.id'), nullable=False)
    name = Column(String(150), nullable=False)
    code = Column(String(40), unique=True, nullable=False)


class Machine(Identity, Created, Base):
    __tablename__ = 'machines'
    station_id = Column(ForeignKey('stations.id'), nullable=False)
    machine_code = Column(String(50), unique=True, nullable=False)
    machine_name = Column(String(150), nullable=False)
    manufacturer = Column(String(100), default='')
    model = Column(String(100), default='')
    serial_number = Column(String(100), default='')
    status = Column(String(30), default='OPERATIONAL')
    critical_temperature = Column(Float, default=100)
    warning_temperature = Column(Float, default=80)
    critical_vibration = Column(Float, default=10)
    warning_vibration = Column(Float, default=7)
    reorder_level = Column(Float, default=10)
    is_critical = Column(Boolean, default=False)


class Shift(Identity, Base):
    __tablename__ = 'shifts'
    factory_id = Column(ForeignKey('factories.id'), nullable=False)
    name = Column(String(80), nullable=False)
    start_time = Column(String(5), nullable=False)
    end_time = Column(String(5), nullable=False)


class User(Identity, Created, Base):
    __tablename__ = 'users'
    name = Column(String(100), nullable=False)
    employee_id = Column(String(40), unique=True, nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    role_id = Column(ForeignKey('roles.id'), nullable=False)
    department_id = Column(ForeignKey('departments.id'), nullable=False)
    factory_id = Column(ForeignKey('factories.id'), nullable=False)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class Report(Identity, Created, Base):
    __tablename__ = 'reports'
    report_number = Column(String(50), unique=True)
    reporter_id = Column(ForeignKey('users.id'), nullable=False)
    factory_id = Column(ForeignKey('factories.id'), nullable=False)
    production_line_id = Column(ForeignKey('production_lines.id'), nullable=False)
    station_id = Column(ForeignKey('stations.id'), nullable=False)
    machine_id = Column(ForeignKey('machines.id'), nullable=False)
    shift_id = Column(ForeignKey('shifts.id'))
    input_type = Column(String(20), nullable=False)
    transcript = Column(Text, default='')
    description = Column(Text, nullable=False)
    language = Column(String(20), default='English')


class AudioFile(Identity, Created, Base):
    __tablename__ = 'audio_files'
    report_id = Column(ForeignKey('reports.id'), nullable=False)
    file_path = Column(String(255), nullable=False)
    original_filename = Column(String(200), nullable=False)
    mime_type = Column(String(100), nullable=False)
    duration = Column(Float)


class Attachment(Identity, Created, Base):
    __tablename__ = 'attachments'
    report_id = Column(ForeignKey('reports.id'), nullable=False)
    filename = Column(String(200), nullable=False)
    file_path = Column(String(255), nullable=False)
    file_type = Column(String(100), nullable=False)
    uploaded_by = Column(ForeignKey('users.id'), nullable=False)


class IssueCategory(Identity, Base):
    __tablename__ = 'issue_categories'
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, default='')
    default_department = Column(ForeignKey('departments.id'), nullable=False)
    default_severity = Column(String(20), default='MEDIUM')
    active = Column(Boolean, default=True)


class Rule(Identity, Created, Base):
    __tablename__ = 'rules'
    name = Column(String(150), nullable=False)
    description = Column(Text, default='')
    rule_type = Column(String(30), nullable=False)
    priority = Column(Integer, default=100)
    active = Column(Boolean, default=True)
    conditions_json = Column(JSON, nullable=False)
    actions_json = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class Keyword(Identity, Base):
    __tablename__ = 'keyword_dictionary'
    language = Column(String(20), nullable=False)
    keyword = Column(String(200), unique=True, nullable=False)
    normalized_keyword = Column(String(200), nullable=False)
    event_code = Column(String(60), nullable=False)
    category_id = Column(ForeignKey('issue_categories.id'), nullable=False)
    severity = Column(String(20), default='MEDIUM')
    active = Column(Boolean, default=True)


class Incident(Identity, Created, Base):
    __tablename__ = 'incidents'
    incident_number = Column(String(50), unique=True)
    report_id = Column(ForeignKey('reports.id'), nullable=False)
    machine_id = Column(ForeignKey('machines.id'), nullable=False)
    category_id = Column(ForeignKey('issue_categories.id'), nullable=False)
    severity = Column(String(20), nullable=False)
    priority = Column(Integer, nullable=False)
    status = Column(String(30), default='ASSIGNED', nullable=False)
    assigned_department_id = Column(ForeignKey('departments.id'), nullable=False)
    assigned_user_id = Column(ForeignKey('users.id'))
    acknowledged_at = Column(DateTime)
    started_at = Column(DateTime)
    resolved_at = Column(DateTime)
    verified_at = Column(DateTime)
    closed_at = Column(DateTime)
    sla_due_at = Column(DateTime, nullable=False)
    matched_rule_ids = Column(JSON, default=list)
    classification = Column(JSON, default=dict)


class IncidentAction(Identity, Created, Base):
    __tablename__ = 'incident_actions'
    incident_id = Column(ForeignKey('incidents.id'), nullable=False)
    user_id = Column(ForeignKey('users.id'))
    action_type = Column(String(40), nullable=False)
    description = Column(Text, nullable=False)


class Comment(Identity, Created, Base):
    __tablename__ = 'comments'
    incident_id = Column(ForeignKey('incidents.id'), nullable=False)
    user_id = Column(ForeignKey('users.id'), nullable=False)
    comment = Column(Text, nullable=False)


class Notification(Identity, Created, Base):
    __tablename__ = 'notifications'
    user_id = Column(ForeignKey('users.id'), nullable=False)
    incident_id = Column(ForeignKey('incidents.id'), nullable=False)
    type = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    read = Column(Boolean, default=False)


class EscalationRule(Identity, Base):
    __tablename__ = 'escalation_rules'
    severity = Column(String(20), nullable=False)
    level = Column(Integer, nullable=False)
    after_minutes = Column(Integer, nullable=False)
    target_role = Column(String(80), nullable=False)
    active = Column(Boolean, default=True)
    __table_args__ = (UniqueConstraint('severity', 'level'),)


class Escalation(Identity, Created, Base):
    __tablename__ = 'escalations'
    incident_id = Column(ForeignKey('incidents.id'), nullable=False)
    level = Column(Integer, nullable=False)
    escalated_to = Column(ForeignKey('users.id'), nullable=False)
    reason = Column(Text, nullable=False)
    __table_args__ = (UniqueConstraint('incident_id', 'level', 'escalated_to'),)


class MachineLog(Identity, Base):
    __tablename__ = 'machine_logs'
    machine_id = Column(ForeignKey('machines.id'), nullable=False)
    timestamp = Column(DateTime, default=utcnow, nullable=False)
    temperature = Column(Float)
    vibration = Column(Float)
    pressure = Column(Float)
    runtime = Column(Float)
    production_count = Column(Integer)
    stock_level = Column(Float)
    status_code = Column(String(40), default='RUNNING')
    raw_payload = Column(JSON, nullable=False)
    __table_args__ = (UniqueConstraint('machine_id', 'timestamp'),)


class MaintenanceDocument(Identity, Created, Base):
    __tablename__ = 'maintenance_documents'
    machine_id = Column(ForeignKey('machines.id'), nullable=False)
    title = Column(String(200), nullable=False)
    document_type = Column(String(60), nullable=False)
    filename = Column(String(200), nullable=False)
    file_path = Column(String(255), nullable=False)
    tags = Column(String(500), default='')
    revision = Column(String(40), default='1')
    uploaded_by = Column(ForeignKey('users.id'), nullable=False)


class AuditLog(Identity, Created, Base):
    __tablename__ = 'audit_logs'
    user_id = Column(ForeignKey('users.id'))
    entity_type = Column(String(80), nullable=False)
    entity_id = Column(Integer)
    action = Column(String(80), nullable=False)
    old_value = Column(JSON)
    new_value = Column(JSON)
    ip_address = Column(String(80), default='')


class SLAPolicy(Identity, Base):
    __tablename__ = 'sla_policies'
    severity = Column(String(20), unique=True, nullable=False)
    minutes = Column(Integer, nullable=False)


class APIKey(Identity, Created, Base):
    __tablename__ = 'api_keys'
    name = Column(String(100), nullable=False)
    key_hash = Column(String(64), unique=True, nullable=False)
    user_id = Column(ForeignKey('users.id'), nullable=False)
    active = Column(Boolean, default=True)


class NotificationSetting(Identity, Base):
    __tablename__ = 'notification_settings'
    user_id = Column(ForeignKey('users.id'), unique=True, nullable=False)
    email_enabled = Column(Boolean, default=False)
