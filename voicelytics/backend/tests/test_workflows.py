from datetime import timedelta
from sqlalchemy import select
from app.database.session import SessionLocal, utcnow
from app.models.entities import Incident, Escalation, Notification, Machine, User, Factory, Report
from app.scheduler.jobs import check_sla


def test_auth_and_permissions(client, auth):
    assert client.get('/api/incidents').status_code == 401
    assert client.post('/api/auth/login', json={'email': 'admin@voicelytics.local', 'password': 'wrong'}).status_code == 401
    headers = auth('operator')
    assert client.get('/api/users', headers=headers).status_code == 403
    assert client.post('/api/machines', headers=headers, json={}).status_code == 403
    assert 'password_hash' not in client.get('/api/auth/me', headers=headers).text


def test_complete_workflow(client, auth):
    technician, engineer, supervisor = auth('technician'), auth('ravi'), auth('supervisor')
    result = client.post('/api/reports', headers=technician, json={'machine_id': 1, 'input_type': 'VOICE', 'description': 'Machine #55-04 has abnormal spindle noise.'})
    assert result.status_code == 200, result.text
    incident = result.json(); ident = incident['id']
    assert incident['severity'] == 'HIGH' and incident['assigned_user'] == 'Engineer Ravi'
    assert incident['matched_rule_ids'] and incident['status'] == 'ASSIGNED'
    uploaded = client.post(f'/api/reports/{incident["report_id"]}/audio', headers=technician, files={'file': ('recording.webm', b'\x1aE\xdf\xa3' + b'test-evidence', 'audio/webm')})
    assert uploaded.status_code == 200, uploaded.text
    assert client.get(f'/api/files/audio/{uploaded.json()["id"]}', headers=engineer).status_code == 200
    assert client.get(f'/api/files/audio/{uploaded.json()["id"]}').status_code == 401
    assert client.post(f'/api/incidents/{ident}/close', headers=supervisor, json={}).status_code == 409
    for action in ['acknowledge', 'start', 'comment', 'resolve']:
        response = client.post(f'/api/incidents/{ident}/{action}', headers=engineer, json={'description': 'Bearing replaced and tested.'})
        assert response.status_code == 200, response.text
    assert client.post(f'/api/incidents/{ident}/verify', headers=engineer, json={}).status_code == 403
    for action in ['verify', 'close']:
        assert client.post(f'/api/incidents/{ident}/{action}', headers=supervisor, json={}).status_code == 200
    detail = client.get(f'/api/incidents/{ident}', headers=supervisor).json()
    assert detail['status'] == 'CLOSED' and len(detail['timeline']) >= 9
    assert any(n['type'] == 'VERIFICATION_REQUIRED' for n in client.get('/api/notifications', headers=supervisor).json())
    assert client.post(f'/api/incidents/{ident}/reopen', headers=supervisor, json={'description': 'Noise returned during next shift'}).json()['status'] == 'ASSIGNED'


def test_threshold_csv_atomic_validation_and_duplicates(client, auth):
    headers = auth()
    csv = 'timestamp,machine_code,temperature\n2026-09-05T10:00:00Z,#55-01,110\n'
    response = client.post('/api/machine-logs/import', headers=headers, files={'file': ('logs.csv', csv, 'text/csv')})
    assert response.status_code == 200, response.text
    incident_id = response.json()['results'][0]['incident_id']
    detail = client.get(f'/api/incidents/{incident_id}', headers=headers).json()
    assert detail['severity'] == 'CRITICAL' and detail['department'] == 'Maintenance'
    assert client.post('/api/machine-logs/import', headers=headers, files={'file': ('logs.csv', csv, 'text/csv')}).status_code == 422
    bad = 'timestamp,machine_code,temperature\n2026-09-06T10:00:00Z,#55-01,110\ninvalid,#55-04,no\n'
    before = len(client.get('/api/machine-logs', headers=headers).json())
    assert client.post('/api/machine-logs/import', headers=headers, files={'file': ('logs.csv', bad, 'text/csv')}).status_code == 422
    assert len(client.get('/api/machine-logs', headers=headers).json()) == before


def test_custom_rule_dictionary_and_sla(client, auth):
    headers = auth()
    payload = {'name': 'Low inventory bearing', 'rule_type': 'THRESHOLD', 'priority': 1, 'conditions_json': {'all': [{'field': 'stock_level', 'op': 'lte', 'value': 10}]}, 'actions_json': {'category': 'Inventory', 'department': 'Stores', 'severity': 'HIGH'}}
    rule = client.post('/api/rules', headers=headers, json=payload)
    assert rule.status_code == 200, rule.text
    result = client.post('/api/machine-logs', headers=headers, json={'machine_code': '#55-04', 'timestamp': '2026-09-05T12:01:00Z', 'stock_level': 7})
    assert result.status_code == 200, result.text
    incident_id = result.json()['incident_id']
    detail = client.get(f'/api/incidents/{incident_id}', headers=headers).json()
    assert detail['category'] == 'Inventory' and detail['severity'] == 'HIGH'
    for text in ['मशीन बंद है', 'मशीन बंद आहे', 'machine band aahe']:
        report = client.post('/api/reports', headers=headers, json={'machine_id': 1, 'description': text}).json()
        assert report['category'] == 'Machine Breakdown'
    with SessionLocal() as db:
        incident = db.get(Incident, incident_id)
        assert 29.9 < (incident.sla_due_at - incident.created_at).total_seconds() / 60 < 30.1
        check_sla(db, utcnow() + timedelta(hours=4)); db.commit()
        count = len(list(db.scalars(select(Escalation))))
        check_sla(db, utcnow() + timedelta(hours=4)); db.commit()
        assert len(list(db.scalars(select(Escalation)))) == count
        assert db.scalar(select(Notification).where(Notification.incident_id == incident_id, Notification.type == 'SLA_BREACH'))


def test_documents_filters_audit_and_websocket(client, auth):
    headers = auth()
    upload = client.post('/api/documents', headers=headers, data={'machine_id': 1, 'title': 'Spindle manual', 'tags': 'bearing'}, files={'file': ('manual.txt', b'Inspect bearing each shift.', 'text/plain')})
    assert upload.status_code == 200, upload.text
    assert len(client.get('/api/documents?q=bearing', headers=headers).json()) == 1
    assert client.get('/api/files/documents/' + str(upload.json()['id']), headers=headers).content == b'Inspect bearing each shift.'
    rows = client.get('/api/incidents?severity=CRITICAL', headers=headers).json()
    assert rows and all(r['severity'] == 'CRITICAL' for r in rows)
    assert 'incident_number' in client.get('/api/reports/export?severity=CRITICAL', headers=headers).text
    assert client.get('/api/audit-logs', headers=headers).json()
    ticket = client.post('/api/auth/ws-ticket', headers=headers).json()['ticket']
    with client.websocket_connect('/ws?ticket=' + ticket) as ws:
        client.post('/api/reports', headers=headers, json={'machine_id': 1, 'description': 'Inspect spindle noise now'})
        assert ws.receive_json()['type'] == 'records_changed'
