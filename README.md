# A testing suite providing some useful pytest fixtures

So far there are two fixtures.

## Fixtures

### `expect`

This is a fixture for expect tests in python. It is copied from https://github.com/daninge/pytest-expect-test 
with some small adjustments. You can use it to test the output of a function. Start with the following example:

```python
from testemate.expect_fixture import expect

import pytest

def func(i: int) -> int:
    return i ** 4

def test_function(expect):
    print(func(2))
    expect("""""", debug=True)
```

Setting `debug=True` will make sure that the output is copied into the expect statement:

```python
from testemate.expect_fixture import expect

import pytest

def func(i: int) -> int:
    return i ** 4

def test_function(expect):
    print(func(2))
    expect("""\
16
""", debug=True)
```

Now setting `debug=False` will make sure that the output is not copied into the expect statement and this 
will be the final version of the test.


### `db_setup`

This is a fixture for setting up a local empty database for testing. Make sure you have docker running in the background.
Its use requires the path to the migrations that should be run.
So you have to define it yourself using a fixture called `path_to_migrations`. Here is an example:

```python
from testemate.database_fixture import db_setup

from pathlib import Path

import pytest

@pytest.fixture
def path_to_migrations():
    return Path(__file__).parent / "db" / "migrations"

def test_db(db_setup):
    import psycopg
    conn = psycopg.connect(
        host=db_setup.host, 
        user=db_setup.username, 
        password=db_setup.password, 
        dbname=db_setup.db_name, 
        port=db_setup.port
    )
    # get all names of tables
    with conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
            )
            tables = cursor.fetchall()
            print(tables)
```

## Installation

To install the package, you can use pip:

```bash
pip install git+https://github.com/jonaskobler/testemate.git
```





