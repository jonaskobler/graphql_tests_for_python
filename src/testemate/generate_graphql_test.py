import argparse
import importlib
import json
import random
import string
import sys
import uuid
from typing import Any

from starlette.testclient import TestClient


def fetch_schema(client: TestClient, endpoint: str) -> dict[str, Any]:
    """
    Fetches the GraphQL schema via introspection.

    Args:
        client (TestClient): The test client to use for the request.
        endpoint (str): The GraphQL endpoint path.

    Returns:
        Dict[str, Any]: The introspected schema.

    Raises:
        Exception: If the schema cannot be fetched.
    """
    query = """
        {
          __schema {
            queryType { name }
            mutationType { name }
            types {
              ...FullType
            }
          }
        }

        fragment FullType on __Type {
          kind
          name
          fields(includeDeprecated: true) {
            name
            args {
              ...InputValue
            }
            type {
              ...TypeRef
            }
            isDeprecated
            deprecationReason
          }
          inputFields {
            ...InputValue
          }
          interfaces {
            ...TypeRef
          }
          enumValues(includeDeprecated: true) {
            name
            isDeprecated
            deprecationReason
          }
          possibleTypes {
            ...TypeRef
          }
        }

        fragment InputValue on __InputValue {
          name
          description
          type { ...TypeRef }
          defaultValue
        }

        fragment TypeRef on __Type {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
              ofType {
                kind
                name
              }
            }
          }
        }
    """
    response = client.post(endpoint, json={"query": query})
    if response.status_code != 200:
        raise Exception(f"Failed to fetch schema: Status code {response.status_code}")
    data = response.json()
    if "errors" in data:
        raise Exception(f"Schema introspection errors: {data['errors']}")
    return response.json()["data"]["__schema"]


# This could be used to generate mock values
def generate_mock_value(type_name: str):
    if type_name == "String":
        return "".join(random.choice(string.ascii_letters) for _ in range(8))
    elif type_name == "Int":
        return random.randint(1, 100)
    elif type_name == "Float":
        return round(random.uniform(1.0, 100.0), 2)
    elif type_name == "Boolean":
        return random.choice([True, False])
    elif type_name == "ID":
        return str(random.randint(1, 1000))
    elif type_name == "UUID":
        return "123e4567-e89b-12d3-a456-426614174000"
        return str(uuid.uuid4())
    else:
        return None


# Function to generate a selection set for a given type
def generate_selection_set(
    type_name: str, schema: dict[str, Any], indent: int = 4
) -> str:
    """
    Generates a selection set string for a given GraphQL type.

    Args:
        type_name (str): The name of the GraphQL type.
        schema (Dict[str, Any]): The introspected schema.
        indent (int, optional): The indentation.

    Returns:
        str: The selection set string.
    """
    selection_set = []
    indentation = " " * indent
    for type_def in schema["types"]:
        if type_def["name"] == type_name and type_def["kind"] == "OBJECT":
            for field in type_def.get("fields", []):
                field_type = field["type"]

                # Handle nested types and lists
                if field_type["kind"] == "OBJECT":
                    sub_selection = generate_selection_set(
                        field_type["name"], schema, indent + 2
                    )
                    selection_set.append(
                        f"{indentation}{field['name']} {{\n{sub_selection}\n{indentation}}}"
                    )
                elif (
                    field_type["kind"] == "LIST"
                    and field_type["ofType"]["kind"] == "OBJECT"
                ):
                    sub_selection = generate_selection_set(
                        field_type["ofType"]["name"], schema, indent + 2
                    )
                    selection_set.append(
                        f"{indentation}{field['name']} {{\n{sub_selection}\n{indentation}}}"
                    )
                elif (
                    field_type["kind"] == "NON_NULL"
                    and field_type["ofType"]["kind"] == "OBJECT"
                ):
                    sub_selection = generate_selection_set(
                        field_type["ofType"]["name"], schema, indent + 2
                    )
                    selection_set.append(
                        f"{indentation}{field['name']} {{\n{sub_selection}\n{indentation}}}"
                    )
                else:
                    selection_set.append(f"{indentation}{field['name']}")

    # Join with newlines, ensuring each line is properly indented
    return "\n".join(selection_set)


# Function to determine the correct type name for a field, including nested types
def get_type_name(field_type):
    if field_type["kind"] == "NON_NULL" or field_type["kind"] == "LIST":
        return get_type_name(field_type["ofType"])
    return field_type["name"]


def generate_test_cases(schema: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Generates test cases for all queries and mutations in the schema.

    Args:
        schema (Dict[str, Any]): The introspected schema.

    Returns:
        List[Dict[str, Any]]: A list of test case dictionaries.
    """
    test_cases = []

    for type_def in schema["types"]:
        # Only consider OBJECT types that are Query or Mutation
        if type_def["kind"] == "OBJECT" and type_def["name"] in ["Query", "Mutation"]:
            for field in type_def.get("fields", []):
                # Generate inputs based on the field's arguments
                variables = {}
                for arg in field["args"]:
                    arg_type_name = get_type_name(arg["type"])
                    # variables[arg['name']] = generate_mock_value(arg_type_name)
                    variables[arg["name"]] = "PLEASE ADD INPUT"

                # Determine the return type of the field
                return_type_name = get_type_name(field["type"])

                # Generate the selection set for the return type
                selection_set = generate_selection_set(return_type_name, schema)

                # Generate a query or mutation string
                operation_type = "query" if type_def["name"] == "Query" else "mutation"

                def format_type(type_def):
                    if type_def["kind"] == "NON_NULL":
                        return f"{format_type(type_def['ofType'])}!"
                    elif type_def["kind"] == "LIST":
                        return f"[{format_type(type_def['ofType'])}]"
                    else:
                        return type_def["name"]

                variable_string = ", ".join(
                    [
                        f"${arg['name']}: {format_type(arg['type'])}"
                        for arg in field["args"]
                    ]
                )
                variable_input = ", ".join(
                    [f"{arg['name']}: ${arg['name']}" for arg in field["args"]]
                )

                if variable_string:
                    if selection_set:
                        query_string = (
                            f"{operation_type} {field['name']}({variable_string}) {{\n"
                            f"  {field['name']}({variable_input}) {{\n"
                            f"{selection_set}\n"
                            f"  }}\n"
                            f"}}"
                        )
                    else:
                        query_string = (
                            f"{operation_type} {field['name']}({variable_string}) {{\n"
                            f"  {field['name']}({variable_input})\n"
                            f"}}"
                        )
                else:
                    if selection_set:
                        query_string = (
                            f"{operation_type} {field['name']} {{\n"
                            f"  {field['name']} {{\n"
                            f"{selection_set}\n"
                            f"  }}\n"
                            f"}}"
                        )
                    else:
                        query_string = (
                            f"{operation_type} {field['name']} {{\n"
                            f"  {field['name']}\n"
                            f"}}"
                        )

                test_cases.append(
                    {
                        "name": field["name"],
                        "operation_type": operation_type,
                        "query": query_string,
                        "variables": variables,
                        "expected_output": None,  # Placeholder, since dunno what's happening
                    }
                )
    return test_cases


def write_test_file(
    test_cases: list[dict[str, Any]],
    app_path: str,
    output_path: str,
    endpoint: str,
) -> None:
    """
    Writes the generated test cases into a Python file.

    Args:
        test_cases (List[Dict[str, Any]]): The list of test cases.
        app_path (str): The path to the app instance.
        output_path (str): The output file path.
        endpoint (str): The GraphQL endpoint path.
    """
    module_path, app_name = app_path.rsplit(".", 1)
    with open(output_path, "w") as file:
        file.write("import pytest\n")
        file.write("from starlette.testclient import TestClient\n")
        file.write(f"from {module_path} import {app_name}\n\n\n")
        file.write("@pytest.fixture\n")
        file.write("def client():\n")
        file.write("    return TestClient(app)\n\n\n")

        for i, test_case in enumerate(test_cases):
            test_name = f"test_{test_case['operation_type']}_{test_case['name']}"
            file.write(f"def {test_name}(client, expect):\n")
            file.write("    query = '''\n")
            for line in test_case["query"].splitlines():
                file.write(f"    {line}\n")
            file.write("    '''\n")
            file.write("    variables = {\n")
            for key, value in test_case["variables"].items():
                formatted_value = json.dumps(value, indent=4)
                formatted_value_lines = formatted_value.splitlines()
                file.write(f"        '{key}': {formatted_value_lines[0]}")
                for line in formatted_value_lines[1:]:
                    file.write(f"\n{line}")
                file.write(",\n")
            file.write("    }\n")
            file.write(
                f"    response = client.post('{endpoint}', json={{'query': query, 'variables': variables}})\n"
            )
            file.write("    assert response.status_code == 200\n")
            file.write("    response_data = response.json()\n")
            file.write("    print(response_data)\n")
            file.write('    expect("""""", debug=True)\n\n\n')


def import_app(app_path: str):
    """
    Dynamically imports the app instance from the given path.

    Args:
        app_path (str): Import path to the app instance.

    Returns:
        Any: The imported app instance.

    Raises:
        ImportError: If the app cannot be imported.
        AttributeError: If the app instance is not found in the module.
    """
    module_path, app_name = app_path.rsplit(".", 1)
    try:
        module = importlib.import_module(module_path)
        app = getattr(module, app_name)
        return app
    except (ValueError, ImportError, AttributeError) as e:
        print(f"Error importing app from path '{app_path}': {e}")
        sys.exit(1)


def parse_arguments() -> argparse.Namespace:
    """
    Parses command-line arguments.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Generate pytest test cases for a GraphQL API."
    )
    parser.add_argument(
        "app_path",
        type=str,
        help="Python import path to the Starlette/FastAPI app instance (e.g., 'src.app').",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="generated_tests.py",
        help="Output path for the generated tests file.",
    )
    parser.add_argument(
        "--endpoint",
        "-e",
        type=str,
        default="/graphql",
        help="GraphQL endpoint path.",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()
    app = import_app(args.app_path)
    client = TestClient(app)
    try:
        schema = fetch_schema(client, args.endpoint)
        print("Fetched schema")
    except Exception as e:
        print(f"Error fetching schema: {e}")
        sys.exit(1)
    print("Generating test cases...")
    test_cases = generate_test_cases(schema)
    if not test_cases:
        print("No test cases generated. Check your schema for queries and mutations.")
        sys.exit(1)
    write_test_file(test_cases, args.app_path, args.output, args.endpoint)
    print(f"Test cases written to {args.output}")


if __name__ == "__main__":
    main()
