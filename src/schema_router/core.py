"""Core schema graph data structure and path-finding algorithms for schema_router."""

from collections import deque


class Schema:
    def __init__(self):
        self.tables: dict[str, set[str]] = {}       # table_name -> {columns}
        self.connections: dict[str, set[str]] = {}  # table_name -> {connected tables}

    # --- tables ---

    def add_table(self, table: str, columns: set[str] | None = None):
        if table not in self.tables:
            self.tables[table] = set(columns) if columns is not None else set()
            self.connections[table] = set()

    def remove_table(self, table: str):
        if table in self.tables:
            for neighbor in self.connections[table]:
                self.connections[neighbor].remove(table)
            del self.tables[table]
            del self.connections[table]

    def get_table_names(self) -> list[str]:
        return list(self.tables.keys())

    def get_tables(self) -> dict[str, set[str]]:
        return self.tables

    # --- columns ---

    def add_column(self, table: str, column: str):
        if table not in self.tables:
            self.add_table(table)
        self.tables[table].add(column)

    def remove_column(self, table: str, column: str):
        if table in self.tables:
            self.tables[table].discard(column)

    def get_columns(self, table: str) -> set[str]:
        return self.tables.get(table, set())

    def has_column(self, table: str, column: str) -> bool:
        return table in self.tables and column in self.tables[table]

    # --- connections ---

    def add_connection(self, from_table: str, to_table: str):
        if from_table not in self.tables:
            self.add_table(from_table)
        if to_table not in self.tables:
            self.add_table(to_table)
        self.connections[from_table].add(to_table)
        self.connections[to_table].add(from_table)  # undirected

    def remove_connection(self, from_table: str, to_table: str):
        if self.has_connection(from_table, to_table):
            self.connections[from_table].remove(to_table)
            self.connections[to_table].remove(from_table)

    def get_connections(self) -> dict[str, set[str]]:
        return self.connections

    def get_all_connections(self) -> list[tuple[str, str]]:
        result: list[tuple[str, str]] = []
        for from_table in self.connections:
            for to_table in self.connections[from_table]:
                result.append((from_table, to_table))
        return result

    def get_connected_tables(self, table: str) -> list[str]:
        return list(self.connections[table])

    def has_connection(self, from_table: str, to_table: str) -> bool:
        return from_table in self.connections and to_table in self.connections[from_table]


def get_all_components(schema: Schema) -> list[set[str]]:
    """Find all connected components of the full schema."""
    remaining = set(schema.get_table_names())
    components: list[set[str]] = []

    while remaining:
        start = next(iter(remaining))
        visited: set[str] = set()
        queue: deque[str] = deque([start])

        while queue:
            vertex = queue.popleft()
            if vertex not in visited:
                visited.add(vertex)
                for neighbor in schema.get_connected_tables(vertex):
                    queue.append(neighbor)

        components.append(visited)
        remaining -= visited

    return components


def _bfs_nearest_target(
    schema: Schema, sources: set[str], targets: set[str]
) -> list[str]:
    """Multi-source BFS. Returns the shortest path from any source to the
    nearest target, inclusive of both endpoints. Empty list if unreachable.
    """
    visited: set[str] = set(sources)
    queue: deque[tuple[str, list[str]]] = deque((s, [s]) for s in sources)

    while queue:
        vertex, path = queue.popleft()
        if vertex in targets:
            return path
        for neighbor in schema.get_connected_tables(vertex):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

    return []


def _connect_component(schema: Schema, component: set[str]) -> set[str]:
    """Greedily connect all required tables in a component, pulling in any
    connector tables along the chosen paths.
    """
    if len(component) == 1:
        return set(component)

    start = next(iter(component))
    result: set[str] = {start}
    unconnected = component - {start}

    while unconnected:
        path = _bfs_nearest_target(schema, result, unconnected)
        if not path:
            break
        result.update(path)
        unconnected -= set(path)

    return result


def find_minimum_subset(schema: Schema, required_tables: list[str]) -> list[list[str]]:
    """Find the minimum set of tables connecting the required tables.

    Required tables are grouped into connected components, and each component
    is connected independently. Returns a list of components, where each
    component is a sorted list of tables (required + connectors).
    """
    required = set(required_tables)
    if not required:
        raise ValueError("required_tables must contain at least one table.")

    if len(required) == 1:
        return [sorted(required)]

    result: list[list[str]] = []
    for component in get_all_components(schema):
        group = required & component
        if group:
            result.append(sorted(_connect_component(schema, group)))
    return result


def get_minimal_subschema(schema_def: dict[str, dict[str, list[str]]], subset: list[str]) -> list[str]:
    """Return the minimum set of tables and columns needed to answer a query.

    Builds a schema graph from schema_def, finds the minimum connecting subset
    of tables for all tables referenced in subset, and returns the result
    sorted by table name then column name.

    Connector tables pulled in to bridge required tables appear as '*.table_name'
    since no specific columns were requested for them.

    Args:
        schema_def: Full database schema as a nested dictionary.
            Each key is a table name. Each value is a dict with:
                columns     (list[str]): Column names in the table.
                connections (list[str]): Tables this table has a FK
                                         relationship with. Relationships
                                         are undirected — declaring A -> B
                                         is sufficient.
            Example:
                {
                    "orders": {
                        "columns":     ["order_id", "customer_id"],
                        "connections": ["customers", "order_items"]
                    },
                    ...
                }

        subset: Column references in 'column_name.table_name' format
            representing the columns relevant to the query.
            Example:
                ["email.customers", "order_date.orders"]

    Returns:
        Flat list of strings sorted by table name then column name:
            "column_name.table_name"  for requested columns.
            "*.table_name"            for connector tables.
        Example:
            ["email.customers", "*.order_items", "order_date.orders"]

    Raises:
        ValueError: If subset is empty.
        ValueError: If an entry does not match 'column_name.table_name' format.
        ValueError: If a table referenced in subset is not in schema_def.

    Examples:
        Direct connection — no connector needed:
            >>> get_minimal_subschema(schema, ["email.customers", "order_date.orders"])
            ['email.customers', 'order_date.orders']

        Connector pulled in automatically:
            >>> get_minimal_subschema(schema, ["order_date.orders", "name.products"])
            ['*.order_items', 'order_date.orders', 'name.products']

        Long chain — multiple connectors:
            >>> get_minimal_subschema(schema, ["email.customers", "description.categories"])
            ['description.categories', 'email.customers', '*.order_items', '*.orders', '*.products']
    """
    if not subset:
        raise ValueError("subset must contain at least one column reference.")

    # Build schema — two passes so all tables exist before connections are added
    schema = Schema()
    for table, data in schema_def.items():
        schema.add_table(table, set(data.get("columns", [])))
    for table, data in schema_def.items():
        for connection in data.get("connections", []):
            schema.add_connection(table, connection)

    # Parse columns and group by table
    table_columns: dict[str, list[str]] = {}
    for entry in subset:
        parts = entry.split(".", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(
                f"Invalid format: '{entry}'. Expected 'column_name.table_name'."
            )
        table = parts[1]
        table_columns.setdefault(table, []).append(entry)

    # Validate all referenced tables exist in schema
    for table in table_columns:
        if table not in schema.get_table_names():
            raise ValueError(f"Table '{table}' not found in schema.")

    # Find minimum connecting subset
    components = find_minimum_subset(schema, list(table_columns.keys()))

    # Build output sorted by (table_name, column_name)
    output: list[tuple[str, str, str]] = []
    for component in components:
        for table in component:
            if table in table_columns:
                for col_ref in table_columns[table]:
                    output.append((table, col_ref.split(".", 1)[0], col_ref))
            else:
                output.append((table, "*", f"*.{table}"))

    output.sort(key=lambda x: (x[0], x[1]))
    return [item[2] for item in output]