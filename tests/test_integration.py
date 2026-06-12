import pytest
from schema_router import get_minimal_subschema


@pytest.fixture
def schema_def() -> dict[str, dict[str, list[str]]]:
    return {
        "customers":   {"columns": ["customer_id", "name", "email"],               "connections": ["orders"]},
        "orders":      {"columns": ["order_id", "customer_id", "order_date"],      "connections": ["customers", "order_items"]},
        "order_items": {"columns": ["order_id", "product_id", "quantity"],         "connections": ["orders", "products"]},
        "products":    {"columns": ["product_id", "name", "category_id"],          "connections": ["order_items", "categories"]},
        "categories":  {"columns": ["category_id", "name", "description"],         "connections": ["products"]},
        "audit_logs":  {"columns": ["log_id", "event_type", "timestamp"],          "connections": []},
    }


def test_single_column_single_table(schema_def):
    # No joins needed — one table, one column
    result = get_minimal_subschema(schema_def, ["email.customers"])
    assert result == ["email.customers"]


def test_multiple_columns_single_table_sorted(schema_def):
    # Columns from one table must be sorted by column name
    result = get_minimal_subschema(
        schema_def,
        ["order_date.orders", "order_id.orders", "customer_id.orders"]
    )
    assert result == ["customer_id.orders", "order_date.orders", "order_id.orders"]


def test_two_directly_connected_tables(schema_def):
    # orders and customers share a direct FK — no connector needed
    result = get_minimal_subschema(
        schema_def,
        ["order_date.orders", "email.customers"]
    )
    assert result == ["email.customers", "order_date.orders"]


def test_two_tables_one_connector(schema_def):
    # orders and products require order_items as connector
    result = get_minimal_subschema(
        schema_def,
        ["order_date.orders", "name.products"]
    )
    assert result == ["*.order_items", "order_date.orders", "name.products"]


def test_two_tables_three_connectors(schema_def):
    # customers and categories require orders, order_items, products as connectors
    result = get_minimal_subschema(
        schema_def,
        ["email.customers", "description.categories"]
    )
    assert result == [
        "description.categories",
        "email.customers",
        "*.order_items",
        "*.orders",
        "*.products"
    ]


def test_three_non_adjacent_tables_one_connector(schema_def):
    # customers, order_items, products — orders needed as connector between
    # customers and order_items; order_items and products are directly connected
    result = get_minimal_subschema(
        schema_def,
        ["email.customers", "quantity.order_items", "name.products"]
    )
    assert result == [
        "email.customers",
        "quantity.order_items",
        "*.orders",
        "name.products"
    ]


def test_multiple_columns_from_two_tables_with_connector(schema_def):
    # Multiple columns from orders and products — order_items is connector
    result = get_minimal_subschema(
        schema_def,
        ["order_date.orders", "customer_id.orders", "name.products", "category_id.products"]
    )
    assert result == [
        "*.order_items",
        "customer_id.orders",
        "order_date.orders",
        "category_id.products",
        "name.products"
    ]


def test_multiple_columns_from_distant_tables(schema_def):
    # Multiple columns from categories and customers — all middle tables are connectors
    result = get_minimal_subschema(
        schema_def,
        ["name.categories", "description.categories", "email.customers", "name.customers"]
    )
    assert result == [
        "description.categories",
        "name.categories",
        "email.customers",
        "name.customers",
        "*.order_items",
        "*.orders",
        "*.products"
    ]


def test_all_connected_tables_required_no_connectors(schema_def):
    # All five connected tables are explicitly required — no connectors needed
    result = get_minimal_subschema(
        schema_def,
        ["customer_id.customers", "order_date.orders", "quantity.order_items",
         "name.products", "name.categories"]
    )
    assert result == [
        "name.categories",
        "customer_id.customers",
        "quantity.order_items",
        "order_date.orders",
        "name.products"
    ]


def test_connector_already_in_required_subset(schema_def):
    # order_items is explicitly required alongside orders and products
    result = get_minimal_subschema(
        schema_def,
        ["order_date.orders", "quantity.order_items", "name.products"]
    )
    assert result == [
        "quantity.order_items",
        "order_date.orders",
        "name.products"
    ]


def test_isolated_table_alone(schema_def):
    # audit_logs has no connections — single table result
    result = get_minimal_subschema(schema_def, ["event_type.audit_logs"])
    assert result == ["event_type.audit_logs"]


def test_isolated_table_with_connected_table(schema_def):
    # audit_logs and orders are in separate components — independent results
    result = get_minimal_subschema(
        schema_def,
        ["event_type.audit_logs", "log_id.audit_logs", "order_date.orders"]
    )
    assert sorted(result) == [
        "event_type.audit_logs",
        "log_id.audit_logs",
        "order_date.orders"
    ]


def test_raises_on_empty_subset(schema_def):
    with pytest.raises(ValueError):
        get_minimal_subschema(schema_def, [])


def test_raises_on_invalid_format(schema_def):
    with pytest.raises(ValueError):
        get_minimal_subschema(schema_def, ["invalid_no_dot"])


def test_raises_on_table_not_in_schema(schema_def):
    with pytest.raises(ValueError, match="not found in schema"):
        get_minimal_subschema(schema_def, ["customer_id.customers", "order_items.product_id"])