from __future__ import annotations

import sqlite3
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

ZOTERO_DB = Path.home() / "Zotero" / "zotero.sqlite"
STORAGE_DIR = Path.home() / "Zotero" / "storage"
TITLE_FIELD_ID = 1
DATE_FIELD_ID = 6
URL_FIELD_ID = 13


@dataclass
class Paper:
    item_id: int
    item_key: str
    title: str
    item_type: str
    date: str | None
    authors: list[str]
    url: str | None


@dataclass
class Collection:
    collection_id: int
    name: str
    parent_id: int | None
    papers: list[Paper] = field(default_factory=list)
    subcollections: list[Collection] = field(default_factory=list)


def _connect() -> sqlite3.Connection:
    db_path = ZOTERO_DB.expanduser().resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"Zotero database not found at {db_path}")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _get_authors(conn: sqlite3.Connection, item_id: int) -> list[str]:
    return [
        r["firstName"] + " " + r["lastName"]
        for r in conn.execute(
            """
            SELECT c.firstName, c.lastName
            FROM itemCreators ic
            JOIN creators c ON ic.creatorID = c.creatorID
            JOIN creatorTypes ct ON ic.creatorTypeID = ct.creatorTypeID
            WHERE ic.itemID = ? AND ct.creatorType = 'author'
            ORDER BY ic.orderIndex
            """,
            (item_id,),
        ).fetchall()
    ]


def get_child_collections(
    conn: sqlite3.Connection, parent_id: int | None
) -> list[sqlite3.Row]:
    if parent_id is None:
        return conn.execute(
            "SELECT collectionID, collectionName, parentCollectionID FROM collections WHERE parentCollectionID IS NULL ORDER BY collectionName"
        ).fetchall()
    return conn.execute(
        "SELECT collectionID, collectionName, parentCollectionID FROM collections WHERE parentCollectionID = ? ORDER BY collectionName",
        (parent_id,),
    ).fetchall()


def get_papers_for_collection(
    conn: sqlite3.Connection, collection_id: int
) -> list[Paper]:
    rows = conn.execute(
        """
        SELECT
            i.itemID, i.key AS item_key,
            COALESCE(idv.value, '(no title)') AS title,
            it.typeName AS item_type,
            date_fields.value AS date,
            url_fields.value AS url
        FROM collectionItems ci
        JOIN items i ON ci.itemID = i.itemID
        JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
        LEFT JOIN itemData id_title ON i.itemID = id_title.itemID AND id_title.fieldID = ?
        LEFT JOIN itemDataValues idv ON id_title.valueID = idv.valueID
        LEFT JOIN itemData id_date ON i.itemID = id_date.itemID AND id_date.fieldID = ?
        LEFT JOIN itemDataValues date_fields ON id_date.valueID = date_fields.valueID
        LEFT JOIN itemData id_url ON i.itemID = id_url.itemID AND id_url.fieldID = ?
        LEFT JOIN itemDataValues url_fields ON id_url.valueID = url_fields.valueID
        WHERE ci.collectionID = ?
        ORDER BY ci.orderIndex
        """,
        (TITLE_FIELD_ID, DATE_FIELD_ID, URL_FIELD_ID, collection_id),
    ).fetchall()

    return [
        Paper(
            item_id=row["itemID"],
            item_key=row["item_key"],
            title=row["title"],
            item_type=row["item_type"],
            date=row["date"],
            authors=_get_authors(conn, row["itemID"]),
            url=row["url"],
        )
        for row in rows
    ]


def get_item_by_key(item_key: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT i.itemID, i.key, it.typeName,
                   idv_title.value AS title,
                   date_fields.value AS date,
                   url_fields.value AS url
            FROM items i
            JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
            LEFT JOIN itemData id_title ON i.itemID = id_title.itemID AND id_title.fieldID = ?
            LEFT JOIN itemDataValues idv_title ON id_title.valueID = idv_title.valueID
            LEFT JOIN itemData id_date ON i.itemID = id_date.itemID AND id_date.fieldID = ?
            LEFT JOIN itemDataValues date_fields ON id_date.valueID = date_fields.valueID
            LEFT JOIN itemData id_url ON i.itemID = id_url.itemID AND id_url.fieldID = ?
            LEFT JOIN itemDataValues url_fields ON id_url.valueID = url_fields.valueID
            WHERE i.key = ?
            """,
            (TITLE_FIELD_ID, DATE_FIELD_ID, URL_FIELD_ID, item_key),
        ).fetchone()
        if row is None:
            return None
        return dict(row)


def get_paper_metadata(item_key: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT itemID FROM items WHERE key = ?", (item_key,)
        ).fetchone()
        if row is None:
            return None
        item_id = row["itemID"]

        item = dict(
            conn.execute(
                """
                SELECT i.key, i.dateAdded, i.dateModified, it.typeName AS item_type
                FROM items i
                JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
                WHERE i.itemID = ?
                """,
                (item_id,),
            ).fetchone()
        )

        item["fields"] = {
            r["fieldName"]: r["value"]
            for r in conn.execute(
                """
                SELECT f.fieldName, idv.value
                FROM itemData id
                JOIN fields f ON id.fieldID = f.fieldID
                JOIN itemDataValues idv ON id.valueID = idv.valueID
                WHERE id.itemID = ?
                ORDER BY f.fieldName
                """,
                (item_id,),
            ).fetchall()
        }

        item["creators"] = [
            {
                "firstName": r["firstName"],
                "lastName": r["lastName"],
                "type": r["creatorType"],
            }
            for r in conn.execute(
                """
                SELECT c.firstName, c.lastName, ct.creatorType
                FROM itemCreators ic
                JOIN creators c ON ic.creatorID = c.creatorID
                JOIN creatorTypes ct ON ic.creatorTypeID = ct.creatorTypeID
                WHERE ic.itemID = ?
                ORDER BY ic.orderIndex
                """,
                (item_id,),
            ).fetchall()
        ]

        item["collections"] = [
            r["collectionName"]
            for r in conn.execute(
                """
                SELECT c.collectionName
                FROM collectionItems ci
                JOIN collections c ON ci.collectionID = c.collectionID
                WHERE ci.itemID = ?
                ORDER BY c.collectionName
                """,
                (item_id,),
            ).fetchall()
        ]

        item["attachments"] = [
            {
                "contentType": r["contentType"],
                "filename": r["path"].removeprefix("storage:") if r["path"] else None,
                "storage_key": r["storage_key"],
            }
            for r in conn.execute(
                """
                SELECT ia.contentType, ia.path, i.key AS storage_key
                FROM itemAttachments ia
                JOIN items i ON ia.itemID = i.itemID
                WHERE ia.parentItemID = ?
                """,
                (item_id,),
            ).fetchall()
        ]

        return item


def get_pdf_path(item_key: str) -> Path | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT itemID FROM items WHERE key = ?", (item_key,)
        ).fetchone()
        if row is None:
            return None
        item_id = row["itemID"]

        att = conn.execute(
            """
            SELECT ia.path, i.key AS storage_key
            FROM itemAttachments ia
            JOIN items i ON ia.itemID = i.itemID
            WHERE ia.parentItemID = ? AND ia.contentType = 'application/pdf'
            """,
            (item_id,),
        ).fetchone()
        if att is None:
            return None

    filename = att["path"].removeprefix("storage:")
    pdf_path = STORAGE_DIR / att["storage_key"] / filename
    return pdf_path if pdf_path.exists() else None


def read_paper_text(item_key: str) -> str | None:
    pdf_path = get_pdf_path(item_key)
    if pdf_path is None:
        return None
    result = subprocess.run(
        ["pdftotext", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext failed: {result.stderr.strip()}")
    return result.stdout


def build_collection_tree(query: str | None = None) -> list[Collection]:
    with _connect() as conn:
        root_rows = get_child_collections(conn, None)
        trees = [_build_subtree(conn, row) for row in root_rows]
        if query:
            trees = _filter_tree(trees, query.lower())
        return trees


def _build_subtree(conn: sqlite3.Connection, row: sqlite3.Row) -> Collection:
    col = Collection(
        collection_id=row["collectionID"],
        name=row["collectionName"],
        parent_id=row["parentCollectionID"],
        papers=get_papers_for_collection(conn, row["collectionID"]),
    )
    child_rows = get_child_collections(conn, row["collectionID"])
    col.subcollections = [_build_subtree(conn, child) for child in child_rows]
    return col


def _filter_tree(collections: list[Collection], query: str) -> list[Collection]:
    filtered = []
    for col in collections:
        sub = _filter_tree(col.subcollections, query)
        keep_by_name = query in col.name.lower()
        keep_by_paper = any(query in p.title.lower() for p in col.papers)
        keep_by_author = any(query in a.lower() for p in col.papers for a in p.authors)
        if keep_by_name or keep_by_paper or keep_by_author or sub:
            col.subcollections = sub
            if not (keep_by_name or keep_by_paper or keep_by_author):
                col.papers = []
            filtered.append(col)
    return filtered


def format_collection_tree(collections: list[Collection], indent: str = "") -> str:
    lines: list[str] = []
    for i, col in enumerate(collections):
        is_last = i == len(collections) - 1
        connector = "└── " if is_last else "├── "
        prefix = indent + connector
        lines.append(f"{prefix}{col.name} ({len(col.papers)} papers)")

        sub_indent = indent + ("    " if is_last else "│   ")
        if col.subcollections:
            lines.append(format_collection_tree(col.subcollections, sub_indent))

        for paper in col.papers:
            author_str = paper.authors[0] if paper.authors else "Unknown"
            year_str = paper.date[:4] if paper.date else "n.d."
            lines.append(
                f"{sub_indent}  [{paper.item_type}] {paper.title} ({year_str}) - {author_str}"
            )
    return "\n".join(lines)
