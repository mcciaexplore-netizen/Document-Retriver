import re
import unicodedata
import operator
from sqlalchemy import select
from app.models.entities import Rule, Keyword

RANK = {'LOW': 1, 'WARNING': 2, 'MEDIUM': 3, 'HIGH': 4, 'CRITICAL': 5}
OPS = {'eq': operator.eq, 'gte': operator.ge, 'gt': operator.gt, 'lte': operator.le, 'lt': operator.lt}


def normalize(text):
    text = unicodedata.normalize('NFKC', text).lower()
    text = ''.join(str(unicodedata.digit(c)) if c.isdigit() else c for c in text)
    text = re.sub(r'#?\s*(\d+)\s*[-–]\s*(\d+)', r'\1-\2', text)
    return ' '.join(''.join(c if c.isalnum() or c.isspace() or c == '-' or unicodedata.category(c).startswith('M') else ' ' for c in text).split())


def contains(text, phrase):
    return f' {normalize(phrase)} ' in f' {normalize(text)} '


def evaluate(db, data, machine, rules=None):
    text = normalize(data.get('text', ''))
    events, dictionary_reasons = [], []
    for keyword in db.scalars(select(Keyword).where(Keyword.active.is_(True)).order_by(Keyword.id)):
        if contains(text, keyword.keyword):
            events.append(keyword.event_code)
            text += ' ' + normalize(keyword.normalized_keyword)
            dictionary_reasons.append(f'Dictionary #{keyword.id}: "{keyword.keyword}" maps to {keyword.event_code}')
    context = {**data, 'text': text, 'event_codes': events}
    enabled = rules if rules is not None else list(db.scalars(select(Rule).where(Rule.active.is_(True)).order_by(Rule.priority, Rule.id)))
    matches = []

    def condition(c):
        actual = context.get(c['field'])
        expected = c['value']
        if isinstance(expected, str) and expected.startswith('machine.'):
            expected = getattr(machine, expected.split('.')[1])
        if actual is None:
            return False, ''
        if c['op'] == 'contains_any':
            found = [v for v in expected if (v in actual if isinstance(actual, list) else contains(str(actual), v))]
            return bool(found), f'{c["field"]} matched: {", ".join(found)}'
        try:
            matched = OPS[c['op']](actual, expected)
        except (TypeError, KeyError):
            matched = False
        return matched, f'{c["field"]} {actual} {c["op"]} {expected}'

    for rule in sorted(enabled, key=lambda r: (r.priority, r.id or 0)):
        if not rule.active:
            continue
        all_results = [condition(c) for c in rule.conditions_json.get('all', [])]
        any_results = [condition(c) for c in rule.conditions_json.get('any', [])]
        if (all_results or any_results) and all(x[0] for x in all_results) and (not any_results or any(x[0] for x in any_results)):
            matches.append({'rule_id': rule.id, 'name': rule.name, 'reasons': [x[1] for x in all_results + any_results if x[0]], 'actions': rule.actions_json})
    result = {'matched_rule_ids': [m['rule_id'] for m in matches], 'category': 'Production', 'severity': 'LOW', 'priority': 4,
              'responsible_department': 'Production', 'alerts': [], 'escalation_required': False,
              'create_incident': bool(data.get('text')), 'matches': matches, 'reasons': dictionary_reasons}
    if matches:
        # Highest severity wins; rule priority/order breaks ties. Lower-severity rules cannot hide safety alerts.
        winner = max(matches, key=lambda m: RANK[m['actions']['severity']])
        actions = winner['actions']
        result.update(category=actions['category'], severity=actions['severity'], priority=actions.get('priority', 3), responsible_department=actions['department'])
        result['create_incident'] = any(m['actions'].get('create_incident', True) for m in matches)
        result['escalation_required'] = any(m['actions'].get('escalation_required', False) for m in matches)
        result['alerts'] = [a for m in matches for a in m['actions'].get('alerts', [])]
        result['reasons'].append(f'Highest matched severity wins; priority breaks ties. Selected rule #{winner["rule_id"]}.')
    else:
        result['reasons'].append('No configured rule matched. Manual reports route to Production at LOW severity; normal logs create no incident.')
    if machine.is_critical and result['category'] == 'Abnormal Noise' and RANK[result['severity']] < RANK['HIGH']:
        result.update(severity='HIGH', priority=2)
        result['reasons'].append(f'Machine {machine.machine_code} is configured as critical equipment: abnormal noise raised to HIGH.')
    return result
