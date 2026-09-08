"""Deterministic boolean search, indexed retrieval and transparent ranking."""
import heapq
import re
from datetime import datetime, time, timedelta
from fastapi import HTTPException
from sqlalchemy import and_, or_, not_, text, func, bindparam, literal_column
from .models import File, SearchRecord, utcnow
from .config import SEARCH_RESULT_LIMIT


def iso(value):
    return value.isoformat() + "Z" if value else None


def location_for(record):
    return {"sheet": record.sheet_name, "row": record.row_number, "column": record.column_name, "cell": record.cell_coordinate, "page": record.page_number, "slide": record.slide_number, "block": record.metadata_json.get("block"), "header": record.header, "table": record.metadata_json.get("table"), "table_row": record.metadata_json.get("table_row")}


def citation_text(file, location):
    parts = [file.filename]
    if location.get("sheet"):
        parts.append(location["sheet"])
    if location.get("row"):
        parts.append(f"Row {location['row']}")
    if location.get("cell"):
        parts.append(location["cell"])
    if location.get("page"):
        parts.append(f"Page {location['page']}")
    if location.get("slide"):
        parts.append(f"Slide {location['slide']}")
    if location.get("block"):
        parts.append(f"Block {location['block']}")
    if location.get("table"):
        parts.append(f"Table {location['table']} / row {location.get('table_row')}")
    return " → ".join(parts)


def result_json(record, file, score=1, terms=None, breakdown=None):
    location = location_for(record)
    return {"result_id": record.id, "id": record.id, "record_version": iso(record.created_at), "score": round(score, 4), "value": record.value, "content": record.content, "matched_text": record.content, "header": record.header, "record_type": record.record_type, "file": {"id": file.id, "name": file.filename, "type": file.file_type}, "location": location, "citation": {"file_id": file.id, "file_name": file.filename, "file_type": file.file_type, **location, "text": citation_text(file, location)}, "uploaded_at": iso(file.uploaded_at), "source_timestamp": iso(file.last_modified), "highlight_terms": terms or [], "score_breakdown": breakdown or {}, "metadata": record.metadata_json}


class BooleanQuery:
    def __init__(self, query):
        self.tokens = re.findall(r'"[^"\n]+"|\(|\)|[^\s()]+', query)
        self.pos = 0
        self.terms = []
        if query.count('"') % 2:
            raise HTTPException(422, "Close the quotation mark to search an exact phrase.")
        self.tree = self.parse_or() if self.tokens else None
        if self.pos != len(self.tokens):
            raise HTTPException(422, "Check the Boolean search syntax and parentheses.")

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def parse_or(self):
        node = self.parse_and()
        while self.peek() == "OR":
            self.pos += 1
            node = ("or", node, self.parse_and())
        return node

    def parse_and(self):
        node = self.parse_not()
        while self.peek() not in (None, ")", "OR"):
            if self.peek() == "AND":
                self.pos += 1
            node = ("and", node, self.parse_not())
        return node

    def parse_not(self):
        token = self.peek()
        if token is None or token in ("AND", "OR", ")"):
            raise HTTPException(422, "A search term is required after a Boolean operator.")
        self.pos += 1
        if token == "NOT":
            return ("not", self.parse_not())
        if token == "(":
            node = self.parse_or()
            if self.peek() != ")":
                raise HTTPException(422, "Close the parentheses in your Boolean query.")
            self.pos += 1
            return node
        term = token.strip('"').casefold()
        self.terms.append(term)
        return ("term", term)


def escaped(term):
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_predicate(tree, dialect):
    if tree is None:
        return True
    operator = tree[0]
    if operator == "and":
        return and_(search_predicate(tree[1], dialect), search_predicate(tree[2], dialect))
    if operator == "or":
        return or_(search_predicate(tree[1], dialect), search_predicate(tree[2], dialect))
    if operator == "not":
        return not_(search_predicate(tree[1], dialect))
    term = tree[1]
    # Indexed token/phrase lookup plus substring matching for IDs and partial words.
    substring = SearchRecord.normalized_content.like(f"%{escaped(term)}%", escape="\\")
    if not re.search(r"\w", term):
        return substring
    if dialect == "sqlite":
        # Each term needs a distinct bound parameter when combined in a Boolean tree.
        indexed = SearchRecord.id.in_(text("SELECT rowid FROM records_fts WHERE records_fts MATCH :fts_term").bindparams(bindparam("fts_term", '"' + term.replace('"', '""') + '"', unique=True)))
    else:
        indexed = func.to_tsvector(literal_column("'simple'"), SearchRecord.normalized_content).op("@@")(func.phraseto_tsquery(literal_column("'simple'"), term))
    number = term.replace(",", "").lstrip("₹$€£")
    if re.fullmatch(r"-?\d+(?:\.\d+)?", number):
        return or_(indexed, substring, SearchRecord.numeric_value == float(number))
    return or_(indexed, substring)


def run_search(db, request):
    query_text = request.query.strip()
    numeric_conditions = []
    def extract_numeric(match):
        numeric_conditions.append((match.group(1).lower(), float(match.group(2).replace(",", ""))))
        return " "
    cleaned = re.sub(r"\b(above|below|over|under|at least|at most)\s+[₹$]?\s*(-?\d[\d,]*(?:\.\d+)?)", extract_numeric, query_text, flags=re.I)
    parsed = BooleanQuery(cleaned)
    filters = request.filters
    query = db.query(SearchRecord, File).join(File, File.id == SearchRecord.file_id).filter(SearchRecord.workspace_id == request.workspace_id, File.processing_status == "indexed")
    if filters.file_type:
        query = query.filter(File.file_type == filters.file_type.lower().lstrip("."))
    if filters.file_id:
        query = query.filter(File.id == filters.file_id)
    if filters.file_name:
        query = query.filter(func.lower(File.filename).like(f"%{escaped(filters.file_name.casefold())}%", escape="\\"))
    if filters.date_from:
        query = query.filter(File.uploaded_at >= datetime.combine(filters.date_from, time.min))
    if filters.date_to:
        query = query.filter(File.uploaded_at < datetime.combine(filters.date_to + timedelta(days=1), time.min))
    if filters.source or filters.source_type:
        query = query.filter(File.source_type == (filters.source or filters.source_type))
    if filters.sheet or filters.sheet_name:
        query = query.filter(SearchRecord.sheet_name == (filters.sheet or filters.sheet_name))
    if filters.page:
        query = query.filter(SearchRecord.page_number == filters.page)
    if filters.slide:
        query = query.filter(SearchRecord.slide_number == filters.slide)
    if filters.category:
        query = query.filter(File.category == filters.category)
    if filters.header:
        query = query.filter(func.lower(SearchRecord.header).like(f"%{escaped(filters.header.casefold())}%", escape="\\"))
    if filters.amount_min is not None:
        query = query.filter(SearchRecord.numeric_value >= filters.amount_min)
    if filters.amount_max is not None:
        query = query.filter(SearchRecord.numeric_value <= filters.amount_max)
    if filters.status:
        query = query.filter(File.processing_status == filters.status)
    if filters.keyword:
        query = query.filter(SearchRecord.normalized_content.like(f"%{escaped(filters.keyword.casefold())}%", escape="\\"))
    for operator, amount in numeric_conditions:
        query = query.filter({"above": SearchRecord.numeric_value > amount, "over": SearchRecord.numeric_value > amount, "below": SearchRecord.numeric_value < amount, "under": SearchRecord.numeric_value < amount, "at least": SearchRecord.numeric_value >= amount, "at most": SearchRecord.numeric_value <= amount}[operator])
    query = query.filter(search_predicate(parsed.tree, db.bind.dialect.name))
    terms = list(dict.fromkeys(parsed.terms))
    phrase = " ".join(terms)
    total_results, file_ids, heap = 0, set(), []
    limit = min(request.limit, SEARCH_RESULT_LIMIT)
    for record, file in query.yield_per(500):
        total_results += 1
        file_ids.add(file.id)
        denominator = max(len(terms), 1)
        content = record.normalized_content
        metadata = " ".join(str(x) for x in location_for(record).values() if x).casefold()
        components = {"exact_phrase_match": float(bool(phrase and phrase in content)), "keyword_match": sum(term in content for term in terms) / denominator, "header_match": sum(term in (record.header or "").casefold() for term in terms) / denominator, "filename_match": sum(term in file.filename.casefold() for term in terms) / denominator, "metadata_match": sum(term in metadata for term in terms) / denominator, "recency_score": max(0, 1 - (utcnow() - file.uploaded_at).total_seconds() / (365 * 86400))}
        score = sum(components[key] * weight for key, weight in [("exact_phrase_match", .35), ("keyword_match", .25), ("header_match", .15), ("filename_match", .10), ("metadata_match", .10), ("recency_score", .05)])
        result = result_json(record, file, score, terms, {k: round(v, 4) for k, v in components.items()})
        entry = (score, -record.id, result)
        if len(heap) < limit:
            heapq.heappush(heap, entry)
        elif entry[:2] > heap[0][:2]:
            heapq.heapreplace(heap, entry)
    results = [item[2] for item in sorted(heap, key=lambda item: item[:2], reverse=True)]
    primary = results[0] if results else None
    return {"query": request.query, "workspace_id": request.workspace_id, "total_results": total_results, "returned_results": len(results), "truncated": total_results > len(results), "results": results, "summary": {"primary_match": primary, "additional_matches": max(0, total_results - 1), "files_matched": len(file_ids)}, "evidence_summary": {"primary_match": primary, "additional_matches": max(0, total_results - 1), "files_matched": len(file_ids)}, "filters": filters.model_dump(mode="json", exclude_none=True), "searched_at": iso(utcnow())}
