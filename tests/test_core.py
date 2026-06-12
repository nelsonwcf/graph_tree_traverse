import pytest
from schema_router.core import Schema, get_all_components, find_minimum_subset, _bfs_nearest_target, get_minimal_subschema


@pytest.fixture
def schema() -> Schema:
    s = Schema()

    s.add_table("customers",   {"customer_id", "name", "email"})
    s.add_table("orders",      {"order_id", "customer_id", "order_date"})
    s.add_table("order_items", {"order_id", "product_id", "quantity"})
    s.add_table("products",    {"product_id", "name", "category_id"})
    s.add_table("categories",  {"category_id", "name", "description"})
    s.add_table("audit_logs",  {"log_id", "event_type", "timestamp"})

    s.add_connection("orders",      "customers")
    s.add_connection("order_items", "orders")
    s.add_connection("order_items", "products")
    s.add_connection("products",    "categories")

    return s


@pytest.fixture
def schema_def() -> dict:
    return {
        "customers":   {"columns": ["customer_id", "name", "email"],                    "connections": ["orders"]},
        "orders":      {"columns": ["order_id", "customer_id", "order_date"],           "connections": ["customers", "order_items"]},
        "order_items": {"columns": ["order_id", "product_id", "quantity"],              "connections": ["orders", "products"]},
        "products":    {"columns": ["product_id", "name", "category_id"],               "connections": ["order_items", "categories"]},
        "categories":  {"columns": ["category_id", "name", "description"],              "connections": ["products"]},
        "audit_logs":  {"columns": ["log_id", "event_type", "timestamp"],               "connections": []},
    }


# --- table structure ---

def test_schema_initialization():
    s = Schema()
    assert s.get_table_names() == []
    assert s.get_all_connections() == []
    assert s.get_tables() == {}
    assert s.get_connections() == {}

def test_add_table():
    s = Schema()
    s.add_table("A")
    assert s.get_table_names() == ["A"]
    assert s.get_tables() == {"A": set()}

def test_add_table_with_columns():
    s = Schema()
    s.add_table("orders", {"order_id", "customer_id"})
    assert s.get_columns("orders") == {"order_id", "customer_id"}

def test_add_connection():
    s = Schema()
    s.add_connection("A", "B")
    assert set(s.get_table_names()) == {"A", "B"}
    assert s.get_connections() == {"A": {"B"}, "B": {"A"}}
    connections = s.get_all_connections()
    assert ("A", "B") in connections
    assert ("B", "A") in connections

def test_add_duplicate_connection_is_ignored():
    s = Schema()
    s.add_connection("A", "B")
    s.add_connection("A", "B")
    assert s.get_connected_tables("A") == ["B"]
    assert s.get_all_connections().count(("A", "B")) == 1


# --- columns ---

def test_add_column():
    s = Schema()
    s.add_table("orders")
    s.add_column("orders", "order_id")
    assert s.has_column("orders", "order_id") is True

def test_add_column_creates_table_if_missing():
    s = Schema()
    s.add_column("orders", "order_id")
    assert "orders" in s.get_table_names()
    assert s.has_column("orders", "order_id") is True

def test_remove_column():
    s = Schema()
    s.add_table("orders", {"order_id", "customer_id"})
    s.remove_column("orders", "customer_id")
    assert s.has_column("orders", "customer_id") is False
    assert s.has_column("orders", "order_id") is True

def test_has_column_returns_false():
    s = Schema()
    s.add_table("orders")
    assert s.has_column("orders", "nonexistent") is False

def test_get_columns_returns_empty_for_unknown_table():
    s = Schema()
    assert s.get_columns("nonexistent") == set()


# --- has_connection ---

def test_has_connection_returns_true():
    s = Schema()
    s.add_connection("A", "B")
    assert s.has_connection("A", "B") is True
    assert s.has_connection("B", "A") is True

def test_has_connection_returns_false():
    s = Schema()
    s.add_table("A")
    s.add_table("B")
    assert s.has_connection("A", "B") is False

def test_has_connection_missing_table_returns_false():
    s = Schema()
    assert s.has_connection("A", "B") is False


# --- get_connected_tables ---

def test_get_connected_tables():
    s = Schema()
    s.add_connection("A", "B")
    s.add_connection("A", "C")
    assert set(s.get_connected_tables("A")) == {"B", "C"}
    assert s.get_connected_tables("B") == ["A"]
    assert s.get_connected_tables("C") == ["A"]


# --- remove_connection ---

def test_remove_connection():
    s = Schema()
    s.add_connection("A", "B")
    s.remove_connection("A", "B")
    assert s.has_connection("A", "B") is False
    assert s.has_connection("B", "A") is False

def test_remove_connection_leaves_tables():
    s = Schema()
    s.add_connection("A", "B")
    s.remove_connection("A", "B")
    assert "A" in s.get_table_names()
    assert "B" in s.get_table_names()


# --- remove_table ---

def test_remove_table():
    s = Schema()
    s.add_connection("A", "B")
    s.remove_table("A")
    assert "A" not in s.get_table_names()
    assert s.has_connection("B", "A") is False

def test_remove_table_leaves_other_connections():
    s = Schema()
    s.add_connection("A", "B")
    s.add_connection("B", "C")
    s.remove_table("A")
    assert s.has_connection("B", "C") is True


# --- get_all_components ---

def test_get_all_components_empty_schema():
    s = Schema()
    assert get_all_components(s) == []

def test_get_all_components_single_component():
    s = Schema()
    s.add_connection("A", "B")
    s.add_connection("B", "C")
    components = get_all_components(s)
    assert len(components) == 1
    assert components[0] == {"A", "B", "C"}

def test_get_all_components_all_isolated():
    s = Schema()
    s.add_table("A")
    s.add_table("B")
    s.add_table("C")
    components = get_all_components(s)
    assert len(components) == 3
    assert {"A"} in components
    assert {"B"} in components
    assert {"C"} in components

def test_get_all_components_schema(schema):
    components = get_all_components(schema)
    assert len(components) == 2
    assert {"customers", "orders", "order_items", "products", "categories"} in components
    assert {"audit_logs"} in components


# --- _bfs_nearest_target ---

def test_bfs_nearest_target_single_source():
    s = Schema()
    s.add_connection("A", "X")
    s.add_connection("X", "B")
    path = _bfs_nearest_target(s, {"A"}, {"B"})
    assert path == ["A", "X", "B"]

def test_bfs_nearest_target_multi_source_finds_nearest():
    s = Schema()
    s.add_connection("A", "C")
    s.add_connection("B", "X")
    s.add_connection("X", "D")
    path = _bfs_nearest_target(s, {"A", "B"}, {"C", "D"})
    assert path == ["A", "C"]

def test_bfs_nearest_target_no_path():
    s = Schema()
    s.add_table("A")
    s.add_table("B")
    path = _bfs_nearest_target(s, {"A"}, {"B"})
    assert path == []


# --- find_minimum_subset ---

def test_find_minimum_subset_raises_on_empty(schema):
    with pytest.raises(ValueError):
        find_minimum_subset(schema, [])

def test_find_minimum_subset_single_table(schema):
    assert find_minimum_subset(schema, ["orders"]) == [["orders"]]

def test_find_minimum_subset_direct_connection(schema):
    result = find_minimum_subset(schema, ["orders", "customers"])
    assert result == [["customers", "orders"]]

def test_find_minimum_subset_with_connector(schema):
    result = find_minimum_subset(schema, ["orders", "products"])
    assert result == [["order_items", "orders", "products"]]

def test_find_minimum_subset_full_chain(schema):
    result = find_minimum_subset(schema, ["categories", "customers"])
    assert result == [["categories", "customers", "order_items", "orders", "products"]]

def test_find_minimum_subset_disconnected_table(schema):
    result = find_minimum_subset(schema, ["customers", "audit_logs"])
    assert sorted(result) == [["audit_logs"], ["customers"]]

def test_find_minimum_subset_required_tables_already_include_connector(schema):
    result = find_minimum_subset(schema, ["orders", "order_items", "products"])
    assert result == [["order_items", "orders", "products"]]


# --- get_minimal_subschema ---

def test_get_minimal_subschema_raises_on_empty(schema_def):
    with pytest.raises(ValueError):
        get_minimal_subschema(schema_def, [])

def test_get_minimal_subschema_invalid_format(schema_def):
    with pytest.raises(ValueError):
        get_minimal_subschema(schema_def, ["invalid_format"])

def test_get_minimal_subschema_single_table(schema_def):
    result = get_minimal_subschema(schema_def, ["order_date.orders"])
    assert result == ["order_date.orders"]

def test_get_minimal_subschema_direct_connection(schema_def):
    result = get_minimal_subschema(schema_def, ["order_date.orders", "email.customers"])
    assert result == ["email.customers", "order_date.orders"]

def test_get_minimal_subschema_with_connector(schema_def):
    result = get_minimal_subschema(schema_def, ["order_date.orders", "name.products"])
    assert result == ["*.order_items", "order_date.orders", "name.products"]

def test_get_minimal_subschema_sorted_by_table_then_column(schema_def):
    result = get_minimal_subschema(
        schema_def,
        ["order_date.orders", "customer_id.orders", "email.customers"]
    )
    assert result == ["email.customers", "customer_id.orders", "order_date.orders"]

def test_get_minimal_subschema_disconnected_table(schema_def):
    result = get_minimal_subschema(
        schema_def,
        ["email.customers", "event_type.audit_logs"]
    )
    assert sorted(result) == ["email.customers", "event_type.audit_logs"]

def test_get_minimal_subschema_full_chain(schema_def):
    result = get_minimal_subschema(
        schema_def,
        ["email.customers", "name.categories"]
    )
    assert result == [
        "name.categories",
        "email.customers",
        "*.order_items",
        "*.orders",
        "*.products"
    ]