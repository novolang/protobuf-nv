#!/usr/bin/env python3
"""Write the vectors at the end of tests/oracle_tests.nv: descriptor sets
from protoc and messages serialised by Google's protobuf module, as hex
constants.

The suite reads these constants, so `novo test` needs neither Python
nor protoc.  Run this again after changing tests/proto.

Usage: python3 tools/vectors.py   (needs protobuf and grpcio-tools)
"""
import importlib, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
PROTO = os.path.join(PKG, "tests", "proto")


def compile_protos(work):
    from grpc_tools import protoc
    sets = {}
    for name, files in (("order", ["acme/order.proto", "acme/money.proto"]),
                        ("legacy", ["legacy.proto"])):
        out = os.path.join(work, name + ".pb")
        rc = protoc.main(["protoc", "-I" + PROTO, "--include_imports",
                          "--descriptor_set_out=" + out, "--python_out=" + work] + files)
        if rc != 0:
            raise SystemExit("protoc failed on " + name)
        sets[name] = open(out, "rb").read()
    return sets


def messages(work):
    sys.path.insert(0, work)
    money = importlib.import_module("acme.money_pb2")
    order = importlib.import_module("acme.order_pb2")
    legacy = importlib.import_module("legacy_pb2")
    out = {}
    o = order.Order(id=150, name="testing", deltas=[3, -270, 86942], blob=b"\x00\xff",
                    ratio=0.5, weight=1.5, notes=["x", "ÿ"], count=4294967295,
                    big=18446744073709551615, drift=-9223372036854775808, f32=7, f64=8, sf64=-1,
                    samples=[1.0, -2.5], flags=[True, False], loose=[-1, 2],
                    currency=money.CURRENCY_OLD, history=[1, 7], memo="m", gift=False, loop=True)
    o.total.units = -5
    o.total.currency = money.CURRENCY_EUR
    o.total.nanos = -2147483648
    o.tags["a"] = 1
    o.ledger[-7].units = 9
    o.items.add(units=1)
    o.lines.add(sku="k", qty=3)
    o.parent.id = 1
    o.card = "visa"
    out["order_full"] = o.SerializeToString(deterministic=True)
    out["order_empty"] = order.Order().SerializeToString()
    v = order.Order(id=-1)
    v.voucher.units = 2
    out["order_voucher"] = v.SerializeToString()
    out["order_unknown"] = order.Order(id=1).SerializeToString() + bytes.fromhex("f8060a8a0703616263")
    old = legacy.Old(id=5, label="hi", codes=[1, 2])
    old.extra.depth = 9
    old.Extensions[legacy.flavour] = 3
    out["legacy_old"] = old.SerializeToString()
    return out


MARK = "// ── the vectors: protoc's descriptor sets and Python's messages ──"


def main():
    work = tempfile.mkdtemp(prefix="protobuf-nv-vectors.")
    sets = compile_protos(work)
    msgs = messages(work)
    lines = [MARK, "//", "// tools/vectors.py writes everything below this line from tests/proto.", ""]
    for name, raw in sorted(sets.items()):
        lines.append(f"// The descriptor set of {name}, with its imports.")
        lines.append(f"fn {name}_set_hex() -> Str")
        lines.append(f'    "{raw.hex()}"')
        lines.append("")
    for name, raw in sorted(msgs.items()):
        lines.append(f"// The message {name}.")
        lines.append(f"fn {name}_hex() -> Str")
        lines.append(f'    "{raw.hex()}"')
        lines.append("")
    path = os.path.join(PKG, "tests", "oracle_tests.nv")
    text = open(path).read()
    head = text[:text.index(MARK)] if MARK in text else text.rstrip() + "\n\n"
    open(path, "w").write(head + "\n".join(lines).rstrip() + "\n")
    print("wrote the vectors of tests/oracle_tests.nv: %d sets, %d messages" % (len(sets), len(msgs)))


if __name__ == "__main__":
    main()
