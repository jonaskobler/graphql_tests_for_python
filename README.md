# Automatic GraphQL Test Generator

This script is designed to automatically generate pytest test cases for your GraphQL API. It introspects your GraphQL schema, generates mock queries/mutations, and outputs a Python test file containing all the generated test cases.

## Step 1: Copy the Script into Your Repository

First, copy the `generate_tests.py` script into the root directory of the repository where you want to generate the tests. This directory should be the one containing your `app` instance.

## Step 2: Install Required Dependencies

Before running the script, you need to ensure that all the required Python packages are installed. You can do this by running:

```bash
pip install -r requirements.txt
```

## Step 3: Set the PYTHONPATH Environment Variable

To ensure that the script can properly locate your app instance and any other modules, you need to set the PYTHONPATH environment variable to the current directory, i.e. your repo:

```bash
export PYTHONPATH=.
```

This command sets the PYTHONPATH to the root of your repository, allowing the script to import your app instance correctly.

## Step 4: Run the Script

The script takes command-line arguments:
### Positional Argument:
app_path: The Python import path to the app instance (e.g., "src.app.app", if your app instance is located in src.app).
### Optional Arguments:
--output or -o: Specifies the output file path for the generated tests (defaults to "generated_tests.py").
--endpoint or -e: Specifies the GraphQL endpoint path (defaults to "/graphql").

A sample command is 

```bash
 python tests/generate_graphql_test.py src.app.app --output tests/test_graphql.py --endpoint /graphql
```



