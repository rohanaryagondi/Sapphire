import unittest
from contracts.jsonschema_min import validate

OBJ = {
    "type": "object",
    "required": ["name", "n"],
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string"},
        "n": {"type": "integer"},
        "kind": {"type": "string", "enum": ["a", "b"]},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
}

class TestValidate(unittest.TestCase):
    def test_valid_object_passes(self):
        self.assertEqual(validate({"name": "x", "n": 3, "kind": "a", "tags": ["t"]}, OBJ), [])

    def test_missing_required_reports_path(self):
        errs = validate({"name": "x"}, OBJ)
        self.assertTrue(any("$.n: required field missing" == e for e in errs))

    def test_wrong_type_reports_and_stops_cascade(self):
        errs = validate({"name": "x", "n": "three"}, OBJ)
        self.assertTrue(any("$.n:" in e and "expected type" in e for e in errs))

    def test_bool_is_not_integer(self):
        errs = validate({"name": "x", "n": True}, OBJ)
        self.assertTrue(any("$.n:" in e for e in errs))

    def test_additional_property_rejected(self):
        errs = validate({"name": "x", "n": 1, "extra": 9}, OBJ)
        self.assertTrue(any("$.extra: additional property not allowed" == e for e in errs))

    def test_enum_violation(self):
        errs = validate({"name": "x", "n": 1, "kind": "z"}, OBJ)
        self.assertTrue(any("$.kind:" in e and "enum" in e for e in errs))

    def test_array_items_path(self):
        errs = validate({"name": "x", "n": 1, "tags": ["ok", 5]}, OBJ)
        self.assertTrue(any("$.tags[1]:" in e for e in errs))

    def test_ref_resolves_against_root(self):
        root = {"schemas": {"leaf": {"type": "string"}},
                "type": "object", "properties": {"v": {"$ref": "#/schemas/leaf"}},
                "required": ["v"], "additionalProperties": False}
        self.assertEqual(validate({"v": "s"}, root), [])
        self.assertTrue(validate({"v": 1}, root))

if __name__ == "__main__":
    unittest.main()
