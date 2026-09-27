#!/usr/bin/env python3
"""Check protobuf-nv's generated code against Google's protobuf module.

The script compiles the `.proto` files under tests/proto with protoc (from
grpcio-tools) into a descriptor set and into Python classes.  It runs the
package's generator over the descriptor set, builds a program from the
generated modules, and checks three things in both directions:

  1. every message Python serialises decodes in novo-lang and encodes
     back to the same bytes;
  2. a message novo-lang builds is read by Python with the values that
     were set;
  3. the generated modules pass `novo fmt --check`.

Usage: python3 tools/roundtrip.py   (needs protobuf and grpcio-tools)
"""
import importlib, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
NOVO = os.environ.get("NOVO", os.path.expanduser("~/.novo/bin/novo"))
PROTO = os.path.join(PKG, "tests", "proto")


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stdout + r.stderr)
        raise SystemExit("failed: " + " ".join(cmd))
    return r.stdout


def manifest(name):
    return (f'[package]\nname = "{name}"\nversion = "0.0.1"\nnovo = ">= 0.13.0"\n\n'
            f'[dependencies]\nprotobuf-nv = {{ path = "{PKG}" }}\n')


def messages(pb):
    """The messages Python serialises: an empty one, a full one, one with
    negative and extreme values, and one carrying unknown fields."""
    money = pb.money_pb2
    order = pb.order_pb2
    out = [order.Order()]
    o = order.Order(id=150, name="testing", deltas=[3, -270, 86942], blob=b"\x00\xff",
                    ratio=0.5, weight=1.5, notes=["x", "", "ÿ"], count=4294967295,
                    big=18446744073709551615, drift=-9223372036854775808,
                    f32=4294967295, f64=18446744073709551615, sf64=-1,
                    samples=[1.0, -0.0, 1e300], flags=[True, False, True], loose=[-1, 2],
                    currency=money.CURRENCY_OLD, history=[1, 2, -3, 7], memo="",
                    gift=False, loop=True)
    o.total.units = -5
    o.total.currency = money.CURRENCY_EUR
    o.total.nanos = -2147483648
    o.tags["a"] = 1
    o.ledger[-7].units = 9
    o.items.add(units=1)
    o.items.add()
    o.lines.add(sku="k", qty=3)
    o.parent.id = 1
    o.parent.parent.name = "grand"
    o.card = "visa"
    out.append(o)
    v = order.Order(id=-1)
    v.voucher.units = 2
    out.append(v)
    c = order.Order(cash=-42)
    out.append(c)
    raw = order.Order(id=1).SerializeToString() + bytes.fromhex("f8060a" + "8a0703616263")
    return [m.SerializeToString(deterministic=True) for m in out] + [raw]


BUILT = '''
    var o = acme_order.new_acme_order()
    o.id = 0 - 7
    o.name = "novo"
    o.deltas = [1, 0 - 1]
    o.tags = [AcmeOrderTagsEntry { key: "k", value: 5 }]
    o.payment = Some(AcmeOrderPaymentCash(v: 99))
    o.gift = Some(true)
    o.ratio = 2.25
    o.big = 0 - 1
    o.currency = 2
    o.history = [0, 1]
    o.lines = [AcmeOrderLine { sku: "z", qty: 2, unknown: pbunknown.empty() }]
    o.total = Some(acme_money.new_acme_money())
    match acme_order.encode_acme_order(o)
        Ok(out) => println(bytes.to_hex(out))
        Err(e)  => println("ERR " + e.message())
'''


def main():
    work = tempfile.mkdtemp(prefix="protobuf-nv-rt.")
    pyout = os.path.join(work, "py")
    os.makedirs(pyout)
    desc = os.path.join(work, "order.pb")
    from grpc_tools import protoc
    rc = protoc.main(["protoc", "-I" + PROTO, "--include_imports", "--descriptor_set_out=" + desc,
                      "--python_out=" + pyout, "acme/order.proto", "acme/money.proto"])
    if rc != 0:
        raise SystemExit("protoc failed")
    sys.path.insert(0, pyout)

    class PB:
        money_pb2 = importlib.import_module("acme.money_pb2")
        order_pb2 = importlib.import_module("acme.order_pb2")

    # The generator, run as a program over the descriptor set.
    gen = os.path.join(work, "gen")
    os.makedirs(os.path.join(gen, "src"))
    open(os.path.join(gen, "novo.toml"), "w").write(manifest("gen"))
    open(os.path.join(gen, "src", "main.nv"), "w").write(GEN_MAIN)
    use = os.path.join(work, "use")
    os.makedirs(os.path.join(use, "src"))
    run([NOVO, "pkg", "build"], cwd=gen)
    run([os.path.join(gen, "gen"), desc, os.path.join(use, "src")], cwd=gen)
    generated = sorted(f for f in os.listdir(os.path.join(use, "src")))
    print("generated:", " ".join(generated))
    for f in generated:
        path = os.path.join(use, "src", f)
        before = open(path).read()
        copy = os.path.join(work, "fmt-" + f)
        open(copy, "w").write(before)
        run([NOVO, "fmt", copy])
        if open(copy).read() != before:
            subprocess.run(["diff", path, copy])
            raise SystemExit("novo fmt changes " + f)

    wires = messages(PB)
    body = "\n".join(f'    check("{w.hex()}")' for w in wires)
    main_src = USE_MAIN.replace("@CHECKS@", body).replace("@BUILT@", BUILT)
    open(os.path.join(use, "novo.toml"), "w").write(manifest("use"))
    open(os.path.join(use, "src", "main.nv"), "w").write(main_src)
    run([NOVO, "pkg", "build"], cwd=use)
    lines = run([os.path.join(use, "use")], cwd=use).splitlines()

    failures = 0
    for w, got in zip(wires, lines):
        if got != w.hex():
            failures += 1
            print("MISMATCH\n  python %s\n  novo   %s" % (w.hex(), got))
    built = PB.order_pb2.Order.FromString(bytes.fromhex(lines[len(wires)]))
    expect = {"id": -7, "name": "novo", "deltas": [1, -1], "tags": {"k": 5}, "cash": 99,
              "gift": True, "ratio": 2.25, "big": 18446744073709551615, "currency": 2,
              "history": [0, 1]}
    for k, v in expect.items():
        have = getattr(built, k)
        have = dict(have) if k == "tags" else (list(have) if k in ("deltas", "history") else have)
        if have != v:
            failures += 1
            print("FIELD %s: python read %r, novo set %r" % (k, have, v))
    if built.lines[0].sku != "z" or not built.HasField("total"):
        failures += 1
        print("nested fields did not survive")
    print("%d wire vectors, %d built fields, %d failure(s)" % (len(wires), len(expect), failures))
    if not failures:
        shutil.rmtree(work)
    sys.exit(1 if failures else 0)


GEN_MAIN = '''use std.bytes
use pbdesc
use pbread
use pbgen

fn main() [io, fs]
    let args = env.args()
    let raw = fs.read_bytes(args[1]) ?? bytes.zeros(0)
    match pbdesc.parse_file_set(raw, pbread.default_limits())
        Ok(set) =>
            match pbgen.generate_set(set, pbgen.default_options())
                Ok(files) =>
                    for g in files
                        let _ = fs.write(args[2] + "/" + g.path, g.source)
                Err(e)    => println(e.message())
        Err(e)  => println(e.message())
'''

USE_MAIN = '''use std.bytes
use pbread
use pbunknown
use acme_money
use acme_order

fn check(h: Str) [io]
    let b = bytes.from_hex(h) ?? bytes.zeros(0)
    match acme_order.decode_acme_order(b, pbread.default_limits())
        Ok(m)  =>
            match acme_order.encode_acme_order(m)
                Ok(out) => println(bytes.to_hex(out))
                Err(e)  => println("ERR " + e.message())
        Err(e) => println("ERR " + e.message())

fn main() [io]
@CHECKS@
@BUILT@
'''

if __name__ == "__main__":
    main()
