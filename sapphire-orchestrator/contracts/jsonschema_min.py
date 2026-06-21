"""A stdlib JSON-Schema validator over the subset Sapphire's contracts use:
type, required, properties, additionalProperties:false, enum, items, $ref.
validate(...) returns a list of error-path strings ([] == valid)."""
from __future__ import annotations

_TYPES = {
    "object": dict, "array": list, "string": str,
    "number": (int, float), "integer": int, "boolean": bool, "null": type(None),
}


def _resolve(ref: str, root: dict):
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported $ref {ref!r} (only #/ local refs)")
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def validate(instance, schema, root=None, path="$") -> list[str]:
    if root is None:
        root = schema
    if "$ref" in schema:
        schema = _resolve(schema["$ref"], root)
    errors: list[str] = []

    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        ok = False
        for tt in types:
            py = _TYPES[tt]
            if tt in ("integer", "number") and isinstance(instance, bool):
                continue  # bool is a subclass of int; never a number here
            if isinstance(instance, py):
                ok = True
                break
        if not ok:
            errors.append(f"{path}: expected type {t}, got {type(instance).__name__}")
            return errors  # type wrong → don't cascade into children

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in enum {schema['enum']}")

    if schema.get("type") == "object" and isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                errors.append(f"{path}.{req}: required field missing")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for k in instance:
                if k not in props:
                    errors.append(f"{path}.{k}: additional property not allowed")
        for k, subschema in props.items():
            if k in instance:
                errors += validate(instance[k], subschema, root, f"{path}.{k}")

    if schema.get("type") == "array" and isinstance(instance, list):
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(instance):
                errors += validate(item, item_schema, root, f"{path}[{i}]")

    return errors
