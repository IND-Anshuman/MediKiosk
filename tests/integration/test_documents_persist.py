"""T2.3: document metadata + doctor-queue registry persistence.

SQLite test DB proves the SQLAlchemy layer; Postgres in compose uses the
same models (plan: SQLite for tests, Postgres in real env).
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def db(tmp_path):
    from medikiosk_api.db import Base, init_engine

    engine = init_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)()
    engine.dispose()


def test_document_metadata_persists(db):
    from medikiosk_api.db import DocumentRow

    row = DocumentRow(
        session_id="sess-1",
        object_key="obj/doc-1.png",
        sha256="abc123",
        page_count=2,
        kind="lab",
    )
    db.add(row)
    db.commit()
    db.expire_all()
    got = db.query(DocumentRow).filter_by(session_id="sess-1").one()
    assert got.object_key == "obj/doc-1.png"
    assert got.kind == "lab"
    assert got.sha256 == "abc123"


def test_registry_write_and_query(db):
    from medikiosk_api.db import RegistryRow

    db.add(
        RegistryRow(
            session_id="sess-1",
            token="T-0042",
            name="Sita Devi",
            complaint="fever",
            red_flag=False,
            status="summary_ready",
        )
    )
    db.commit()
    db.expire_all()
    rows = db.query(RegistryRow).filter_by(status="summary_ready").all()
    assert len(rows) == 1 and rows[0].token == "T-0042"


def test_purge_deletes_session_documents(db):
    from medikiosk_api.db import DocumentRow, purge_session_data

    db.add_all(
        [
            DocumentRow(
                session_id="sess-2",
                object_key="obj/a.png",
                sha256="s1",
                page_count=1,
                kind="prescription",
            ),
            DocumentRow(
                session_id="sess-2",
                object_key="obj/b.png",
                sha256="s2",
                page_count=1,
                kind="lab",
            ),
        ]
    )
    db.commit()
    purge_session_data(db, "sess-2")
    assert db.query(DocumentRow).filter_by(session_id="sess-2").count() == 0