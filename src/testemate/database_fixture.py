import logging
from dataclasses import dataclass
from pathlib import Path

import psycopg
from testcontainers.postgres import PostgresContainer
import pytest

logger = logging.getLogger(__name__)

postgres = PostgresContainer("postgres:14-alpine")


def get_up_migrations(filepath: Path) -> list[Path]:
    migration_files = []
    for file in filepath.iterdir():
        if file.name.endswith("up.sql"):
            migration_files.append(file)

    sorted_migration_files = sorted(
        migration_files, key=lambda x: int(x.name.split("_")[0])
    )
    return sorted_migration_files


def execute_sql_script(filename, cursor):
    with open(filename, "r") as fd:
        sql_file = fd.read()
    sql_commands = sql_file.split(";")[:-1]
    for command in sql_commands:
        try:
            cursor.execute(command)
        except Exception as e:
            logger.warning("Command", command, "skipped: ", e)


@dataclass
class DatabaseInfo:
    host: str
    port: str
    username: str
    password: str
    db_name: str


@pytest.fixture
def db_setup(request, path_to_migrations: Path):
    postgres.start()

    def remove_container():
        postgres.stop()

    request.addfinalizer(remove_container)

    port = postgres.get_exposed_port(5432)
    username = postgres.username
    password = postgres.password
    db_name = postgres.dbname

    conn = psycopg.connect(
        host="localhost", user=username, password=password, dbname=db_name, port=port
    )

    info = DatabaseInfo(
        host="localhost",
        port=port,
        username=username,
        password=password,
        db_name=db_name,
    )

    with conn:
        with conn.cursor() as cursor:
            for migration in get_up_migrations(path_to_migrations):
                execute_sql_script(migration, cursor)

    conn.close()

    yield info
