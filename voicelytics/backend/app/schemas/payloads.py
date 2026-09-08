from typing import Literal, Any
from datetime import datetime, timezone
import math
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

Severity = Literal['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'WARNING']


class Payload(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Login(Payload):
    email: str = Field(max_length=200)
    password: str = Field(max_length=100)


class ReportInput(Payload):
    machine_id: int
    shift_id: int | None = None
    input_type: Literal['VOICE', 'MANUAL', 'SYSTEM', 'CSV', 'IMAGE', 'DOCUMENT'] = 'MANUAL'
    description: str = Field(min_length=5, max_length=20000)
    transcript: str = Field(default='', max_length=20000)
    language: Literal['English', 'Hindi', 'Marathi'] = 'English'
    severity_override: Severity | None = None


class ActionInput(Payload):
    description: str = Field(default='', max_length=10000)
    assigned_user_id: int | None = None
    assigned_department_id: int | None = None
    severity: Severity | None = None


class Condition(Payload):
    field: Literal['text', 'event_codes', 'temperature', 'vibration', 'pressure', 'runtime', 'production_count', 'stock_level', 'status_code']
    op: Literal['contains_any', 'eq', 'gte', 'gt', 'lte', 'lt']
    value: Any

    @model_validator(mode='after')
    def valid_operation(self):
        numeric = {'temperature', 'vibration', 'pressure', 'runtime', 'production_count', 'stock_level'}
        refs = {'machine.critical_temperature', 'machine.warning_temperature', 'machine.critical_vibration', 'machine.warning_vibration', 'machine.reorder_level'}
        if self.op == 'contains_any':
            if self.field not in {'text', 'event_codes'} or not isinstance(self.value, list) or not self.value or not all(isinstance(x, str) and x.strip() for x in self.value):
                raise ValueError('contains_any requires text/event_codes and a nonempty string list')
        elif self.field in numeric:
            if not ((isinstance(self.value, (int, float)) and not isinstance(self.value, bool) and math.isfinite(self.value)) or (isinstance(self.value, str) and self.value in refs)):
                raise ValueError('Numeric conditions require a finite number or supported machine threshold')
        elif self.op != 'eq' or not isinstance(self.value, str):
            raise ValueError('Text fields support eq or contains_any')
        return self


class Conditions(Payload):
    all: list[Condition] = Field(default_factory=list, max_length=30)
    any: list[Condition] = Field(default_factory=list, max_length=30)

    @model_validator(mode='after')
    def nonempty(self):
        if not self.all and not self.any:
            raise ValueError('Add at least one condition')
        return self


class RuleActions(Payload):
    category: str = Field(min_length=1, max_length=100)
    department: str = Field(min_length=1, max_length=80)
    severity: Severity
    priority: int = Field(default=3, ge=1, le=5)
    escalation_required: bool = False
    create_incident: bool = True
    alerts: list[str] = Field(default_factory=list, max_length=10)


class RuleInput(Payload):
    name: str = Field(min_length=3, max_length=150)
    description: str = Field(default='', max_length=2000)
    rule_type: Literal['TEXT', 'THRESHOLD', 'EVENT']
    priority: int = Field(default=100, ge=0, le=10000)
    active: bool = True
    conditions_json: Conditions
    actions_json: RuleActions


class LogInput(Payload):
    machine_code: str = Field(min_length=1, max_length=50)
    timestamp: datetime
    temperature: float | None = None
    vibration: float | None = Field(default=None, ge=0)
    pressure: float | None = Field(default=None, ge=0)
    runtime: float | None = Field(default=None, ge=0)
    production_count: int | None = Field(default=None, ge=0)
    stock_level: float | None = Field(default=None, ge=0)
    status_code: Literal['RUNNING', 'STOPPED', 'OFFLINE', 'WARNING', 'CRITICAL'] = 'RUNNING'

    @field_validator('timestamp')
    @classmethod
    def timestamp_utc(cls, value):
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value

    @field_validator('temperature', 'vibration', 'pressure', 'runtime', 'stock_level')
    @classmethod
    def finite(cls, value):
        if value is not None and not math.isfinite(value):
            raise ValueError('Value must be finite')
        return value


class RuleTest(Payload):
    machine_id: int
    text: str = Field(default='', max_length=20000)
    temperature: float | None = None
    vibration: float | None = None
    stock_level: float | None = None
    status_code: str = ''
    rule: RuleInput | None = None


class UserInput(Payload):
    name: str = Field(min_length=2, max_length=100)
    employee_id: str = Field(min_length=1, max_length=40)
    email: str = Field(pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$', max_length=200)
    password: str | None = None
    role_id: int
    department_id: int
    factory_id: int
    is_active: bool = True
