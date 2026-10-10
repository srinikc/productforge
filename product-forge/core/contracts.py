"""A1 canonical contracts (thin) + Go<->Python wire contract (BI-PF-0393).

Single concern: the canonical, language-neutral **contract surface** for the Product Forge
build-time -> EAP -> runtime-package path (``ProductSpec``, ``TechnologyProfile``,
``RuntimeProfile``, ``DeploymentProfile``, ``LicenseProfile``, ``EntitlementProfile``,
``ComponentManifest``, ``BOM``, ``Evidence``) plus the **wire envelope** the Go host and the
Python core exchange.

This module is **types + schema + validation only**: it owns no store and emits nothing on its
own. Canonical data stays in the existing owners (``core.bom``, ``core.packaging``,
``core.licensing``, ``core.tech_stack``, ...) and is projected into these contracts on demand
(see ``core.bom.contract_view``). Grow by need: add a contract because a real producer or
consumer needs it, never speculatively.

The Python side is the schema source of truth; ``product-forge/go/contract`` mirrors the
required-field shape and both are cross-checked by ``test-framework/tests/pipeline/test_contracts.py``.
"""
from __future__ import annotations

import contextlib
import json
import sys
from dataclasses import dataclass
from typing import Any

import jsonschema

SCHEMA_KEY = "schema"
WIRE_VERSION = "1"

# ── declarative field/contract specs (one source -> JSON Schema + canonicalization) ──


@dataclass(frozen=True)
class Field:
    name: str
    type: str = "string"  # string | integer | number | boolean | object | array | enum
    required: bool = False
    enum: tuple[str, ...] = ()
    items: str = "string"  # scalar item type for arrays
    item_fields: tuple[Field, ...] = ()  # object item shape for arrays
    doc: str = ""


@dataclass(frozen=True)
class ContractSpec:
    name: str
    schema_const: str
    title: str
    fields: tuple[Field, ...]
    doc: str = ""

    def field_names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields)

    def required(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields if f.required)


_PRODUCT_SPEC = ContractSpec(
    "product-spec", "product-forge/product-spec@1", "ProductSpec",
    (
        Field("schema", required=True),
        Field("product_id", required=True),
        Field("name", required=True),
        Field("summary"),
        Field("domain"),
        Field("requirements", type="array"),
        Field("capabilities", type="array"),
        Field("editions", type="array"),
        Field("created_at"),
    ),
    "What the platform is asked to produce (requirements -> product).",
)

_TECHNOLOGY_PROFILE = ContractSpec(
    "technology-profile", "product-forge/technology-profile@1", "TechnologyProfile",
    (
        Field("schema", required=True),
        Field("language", required=True),
        Field("framework"),
        Field("database"),
        Field("build_tool"),
        Field("components", type="array"),
        Field("rationale"),
    ),
    "The chosen technology stack for the generated product.",
)

_RUNTIME_PROFILE = ContractSpec(
    "runtime-profile", "product-forge/runtime-profile@1", "RuntimeProfile",
    (
        Field("schema", required=True),
        Field("entrypoint", required=True),
        Field("language", required=True),
        Field("requirements", type="array"),
        Field("env", type="object"),
        Field("resources", type="object"),
        Field("notes"),
    ),
    "How the shipped artifact runs (entrypoint + runtime deps + resources).",
)

_DEPLOYMENT_PROFILE = ContractSpec(
    "deployment-profile", "product-forge/deployment-profile@1", "DeploymentProfile",
    (
        Field("schema", required=True),
        Field("target", required=True),
        Field("provider"),
        Field("distribution", type="enum", required=True,
              enum=("open-source", "commercial", "hosted", "white-label")),
        Field("artifacts", type="array"),
        Field("env", type="object"),
    ),
    "Where/how the package is deployed (target + distribution).",
)

_LICENSE_PROFILE = ContractSpec(
    "license-profile", "product-forge/license-profile@1", "LicenseProfile",
    (
        Field("schema", required=True),
        Field("license_id", required=True),
        Field("tier", required=True),
        Field("distribution", type="enum",
              enum=("open-source", "commercial", "hosted", "white-label")),
        Field("signing", type="enum", enum=("symmetric", "asymmetric", "none")),
        Field("seats", type="integer"),
        Field("issued_at"),
        Field("expires_at"),
    ),
    "The issued license (identity + tier + signing posture + expiry).",
)

_ENTITLEMENT_PROFILE = ContractSpec(
    "entitlement-profile", "product-forge/entitlement-profile@1", "EntitlementProfile",
    (
        Field("schema", required=True),
        Field("tier", required=True),
        Field("groups", type="array"),
        Field("seats", type="integer"),
        Field("max_parallel_projects", type="integer"),
        Field("max_created_projects", type="integer"),
    ),
    "The capability groups + quotas an edition/tier is entitled to.",
)

_COMPONENT_MANIFEST = ContractSpec(
    "component-manifest", "product-forge/component-manifest@1", "ComponentManifest",
    (
        Field("schema", required=True),
        Field("components", type="array", required=True, item_fields=(
            Field("component_id", required=True),
            Field("name"),
            Field("language", type="enum", enum=("python", "go", "rust", "typescript", "other")),
            Field("runtime_required", type="boolean"),
            Field("customer_delivered", type="boolean"),
            Field("compiled", type="boolean"),
            Field("ip_zone", type="enum", enum=("A", "B", "C")),
            Field("license"),
            Field("version"),
        )),
    ),
    "Per-component declaration that drives packaging (language/compiled/ip_zone/license).",
)

_BOM = ContractSpec(
    "bom", "product-forge/bom@1", "BOM",
    (
        Field("schema", required=True),
        Field("project", required=True),
        Field("source_dir"),
        Field("dependencies", type="object"),
        Field("licenses", type="array"),
        Field("footprint", type="object"),
        Field("components", type="array"),
    ),
    "Bill of materials: declared dependencies + licenses + footprint for the package.",
)

_EVIDENCE = ContractSpec(
    "evidence", "product-forge/evidence@1", "Evidence",
    (
        Field("schema", required=True),
        Field("evidence_id", required=True),
        Field("item_id"),
        Field("kind", type="enum", required=True,
              enum=("test", "artifact", "report", "scan", "approval")),
        Field("path"),
        Field("sha256"),
        Field("run_id"),
        Field("created_at"),
    ),
    "Run-bound evidence: what was verified, where it lives, and its hash.",
)

_WIRE_REQUEST = ContractSpec(
    "wire-request", "product-forge/wire-request@1", "WireRequest",
    (
        Field("schema", required=True),
        Field("id", required=True),
        Field("op", type="enum", required=True,
              enum=("ping", "describe", "validate", "canonicalize")),
        Field("contract_name"),
        Field("payload", type="object"),
        Field("source", type="enum", enum=("python", "go")),
    ),
    "Go<->Python request envelope.",
)

_WIRE_RESPONSE = ContractSpec(
    "wire-response", "product-forge/wire-response@1", "WireResponse",
    (
        Field("schema", required=True),
        Field("id", required=True),
        Field("op", required=True),
        Field("ok", type="boolean", required=True),
        Field("status", type="enum", required=True, enum=("ok", "error")),
        Field("host", type="enum", required=True, enum=("python", "go")),
        Field("contract_name"),
        Field("result", type="object"),
        Field("error"),
    ),
    "Go<->Python response envelope.",
)

_SPECS: tuple[ContractSpec, ...] = (
    _PRODUCT_SPEC, _TECHNOLOGY_PROFILE, _RUNTIME_PROFILE, _DEPLOYMENT_PROFILE,
    _LICENSE_PROFILE, _ENTITLEMENT_PROFILE, _COMPONENT_MANIFEST, _BOM, _EVIDENCE,
    _WIRE_REQUEST, _WIRE_RESPONSE,
)

CONTRACTS: dict[str, ContractSpec] = {s.name: s for s in _SPECS}

# The canonical product contracts (fixtures live under fixture sample-product/).
PRODUCT_CONTRACTS: tuple[str, ...] = (
    _PRODUCT_SPEC.name, _TECHNOLOGY_PROFILE.name, _RUNTIME_PROFILE.name,
    _DEPLOYMENT_PROFILE.name, _LICENSE_PROFILE.name, _ENTITLEMENT_PROFILE.name,
    _COMPONENT_MANIFEST.name, _BOM.name, _EVIDENCE.name,
)

WIRE_CONTRACTS: tuple[str, ...] = (_WIRE_REQUEST.name, _WIRE_RESPONSE.name)


# ── schema + validation ─────────────────────────────────────────────────────────
def _field_schema(f: Field, spec: ContractSpec) -> dict[str, Any]:
    if f.name == SCHEMA_KEY:
        return {"type": "string", "const": spec.schema_const}
    if f.type == "enum":
        return {"type": "string", "enum": list(f.enum)}
    if f.type == "array":
        if f.item_fields:
            props = {c.name: _field_schema(c, spec) for c in f.item_fields}
            items: dict[str, Any] = {
                "type": "object",
                "properties": props,
                "required": [c.name for c in f.item_fields if c.required],
                "additionalProperties": False,
            }
        else:
            items = {"type": f.items}
        return {"type": "array", "items": items}
    return {"type": f.type}


def schema(name: str) -> dict[str, Any]:
    """JSON Schema (draft-07) for a canonical contract. Raises KeyError if unknown."""
    spec = CONTRACTS[name]
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": spec.title,
        "description": spec.doc,
        "type": "object",
        "properties": {f.name: _field_schema(f, spec) for f in spec.fields},
        "required": [f.name for f in spec.fields if f.required],
        "additionalProperties": False,
    }


def contract_names() -> list[str]:
    """All contract names (product + wire), in definition order."""
    return [s.name for s in _SPECS]


def required_fields(name: str) -> tuple[str, ...]:
    """The required field names for a contract (used to cross-check the Go mirror)."""
    return CONTRACTS[name].required()


def validate(name: str, data: Any) -> dict[str, Any]:
    """Validate ``data`` against a contract. Fail-closed: unknown contract/payload => invalid."""
    if name not in CONTRACTS:
        return {"valid": False, "contract": name, "errors": [f"unknown contract: {name}"]}
    if not isinstance(data, dict):
        return {"valid": False, "contract": name, "errors": ["payload must be an object"]}
    errors: list[str] = []
    validator = jsonschema.Draft7Validator(schema(name))
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        path = ".".join(str(p) for p in err.absolute_path) or "<root>"
        errors.append(f"{path}: {err.message}")
    return {"valid": not errors, "contract": name, "errors": errors}


def canonical(name: str, data: Any) -> dict[str, Any]:
    """Project ``data`` onto a contract: keep known fields (in declared order) + stamp ``schema``.

    Drops unknown keys so the wire form is stable and thin; never invents values for absent
    optional fields (keeps the result schema-valid). Raises KeyError if the contract is unknown.
    """
    spec = CONTRACTS[name]
    src = data if isinstance(data, dict) else {}
    out: dict[str, Any] = {SCHEMA_KEY: spec.schema_const}
    for f in spec.fields:
        if f.name != SCHEMA_KEY and f.name in src:
            out[f.name] = src[f.name]
    return out


def record(name: str, **values: Any) -> dict[str, Any]:
    """Build a canonical contract object from keyword values (``schema`` is stamped)."""
    return canonical(name, dict(values))


def empty(name: str) -> dict[str, Any]:
    """A minimal canonical instance (``schema`` only) for a contract."""
    return canonical(name, {})


def export_schemas(directory: str) -> list[str]:
    """Write each contract's JSON Schema to ``<directory>/<name>.schema.json`` (best-effort).

    Returns the written paths; raises OSError if the directory cannot be written.
    """
    import os

    os.makedirs(directory, exist_ok=True)
    written: list[str] = []
    for name in contract_names():
        p = os.path.join(directory, f"{name}.schema.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(schema(name), f, indent=2, sort_keys=False)
            f.write("\n")
        written.append(p)
    return written


# ── Go<->Python wire contract ────────────────────────────────────────────────────
def wire_request(op: str, contract_name: str = "", payload: Any = None, *,
                 id: str = "", source: str = "") -> dict[str, Any]:
    """Build a canonical wire-request envelope (fail-closed validation happens on handling).

    ``source`` is only stamped when it is a real enum value (``python``/``go``); an empty source
    is omitted so it stays a valid optional field.
    """
    values: dict[str, Any] = {"id": id, "op": op, "contract_name": contract_name,
                              "payload": payload if isinstance(payload, dict) else {}}
    if source:
        values["source"] = source
    return record("wire-request", **values)


def _wire_response(req_id: str, op: str, ok: bool, status: str, host: str,
                   contract_name: str = "", result: dict[str, Any] | None = None,
                   error: str = "") -> dict[str, Any]:
    return record(
        "wire-response", **{"id": req_id, "op": op, "ok": bool(ok), "status": status,
                            "host": host, "contract_name": contract_name,
                            "result": result or {}, "error": error},
    )


def handle_wire(request: Any, host: str = "python") -> dict[str, Any]:
    """Handle a wire request on the Python core side and return a canonical wire response.

    Never raises: a malformed request yields ``ok=false`` / ``status=error`` (fail-closed).
    """
    req = request if isinstance(request, dict) else {}
    req_id = str(req.get("id") or "")
    op = str(req.get("op") or "")
    cname = str(req.get("contract_name") or "")
    check = validate("wire-request", req)
    if not check["valid"]:
        return _wire_response(req_id, op, False, "error", host,
                              cname, error="invalid wire-request: " + "; ".join(check["errors"][:3]))
    if op == "ping":
        return _wire_response(req_id, op, True, "ok", host,
                              result={"version": WIRE_VERSION, "host": host,
                                      "contracts": contract_names()})
    if op not in ("describe", "validate", "canonicalize"):
        return _wire_response(req_id, op, False, "error", host, cname,
                              error=f"unsupported op: {op}")
    if cname not in CONTRACTS:
        return _wire_response(req_id, op, False, "error", host, cname,
                              error=f"unknown contract: {cname}")
    payload = req.get("payload") if isinstance(req.get("payload"), dict) else {}
    if op == "describe":
        return _wire_response(req_id, op, True, "ok", host, cname,
                              result={"contract": cname, "schema": schema(cname)})
    if op == "validate":
        res = validate(cname, payload)
        return _wire_response(req_id, op, True, "ok", host, cname,
                              result={"contract": cname, "valid": res["valid"],
                                      "errors": res["errors"]})
    return _wire_response(req_id, op, True, "ok", host, cname,
                          result={"contract": cname, "canonical": canonical(cname, payload)})


# ── CLI ──────────────────────────────────────────────────────────────────────────
def _cli(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not args or args[0] in ("-h", "--help"):
        print("Usage:")
        print("  python -m core.contracts list")
        print("  python -m core.contracts schema <contract>")
        print("  python -m core.contracts validate <contract> <json-file>")
        print("  python -m core.contracts export <directory>")
        return 0 if args else 1
    cmd = args[0]
    if cmd == "list":
        for n in contract_names():
            print(n)
        return 0
    if cmd == "schema" and len(args) >= 2:
        print(json.dumps(schema(args[1]), indent=2))
        return 0
    if cmd == "validate" and len(args) >= 3:
        with open(args[2], encoding="utf-8") as f:
            data = json.load(f)
        res = validate(args[1], data)
        print(json.dumps(res, indent=2))
        return 0 if res["valid"] else 1
    if cmd == "export" and len(args) >= 2:
        for p in export_schemas(args[1]):
            print(p)
        return 0
    print(f"unknown command: {' '.join(args)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
