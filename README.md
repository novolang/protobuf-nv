# protobuf-nv

**Status: NOT IMPLEMENTED — interface only.**

Every public function below is published with its signature and its
effect row, and every body is `todo()`.  Installing this package works;
calling it panics with `not implemented`.

## What this is

Protocol Buffers, the encoding under gRPC and under most of the
machine-to-machine traffic inside a data centre.  A message is a
sequence of fields and nothing else: each one a varint KEY, then a
payload whose shape the low three bits of that key announce.  There is
no header, no length, no field count and no end marker — which is why a
message is small, why a reader can walk one it has no schema for, and
why something outside the format always has to say where it stops.

Six surfaces, and a reader should know which one they are on.

| surface | module | reach for it when |
| --- | --- | --- |
| the **wire** | `pbwire` | you are writing a codec, or reading a hexdump |
| the **reader** | `pbread` | bytes arrive and you want fields out |
| the **writer** | `pbwrite` | you have values and want bytes in your own buffer |
| the **kept fields** | `pbunknown` | you forward a message you did not fully understand |
| the **descriptor** | `pbdesc` | you have a `FileDescriptorSet` and want to know what is in it |
| the **dynamic message** | `pbdyn` | there was never a `.proto` file on this machine |
| the **generator** | `pbgen` | you want novo-lang structs out of a `.proto` file |

## Adding it, and checking it

```bash
novo pkg add protobuf-nv     # into your novo.toml
novo pkg build               # type- and effect-check the package
novo test --isolate tests/protobuf_tests.nv
```

`novo test` is red today and that is the point of the release: all
seventy-four assertions fail with `not implemented: <module>.<fn>`.
They turn green one at a time as bodies land.

## The one example that will work

```novo
use std.bytes
use pbread
use pbwrite

fn main() [io]
    // The encoding specification's own first example: field 1, the
    // varint 150.
    let b = pbwrite.builder(pbwrite.build_limits())
    match pbwrite.put_varint(b, 1, 150)
        Ok(b2) =>
            match pbwrite.done(b2)
                Ok(out) => println(bytes.to_hex(out))   // 089601
                Err(e)  => println(e.message())
        Err(e) => println(e.message())
```

## The load-bearing interface

`pbwire.skip_at(src, off, tag) -> Result<Int, PbDecodeError>`.

Every other decision in this package follows from it.  Because a key
announces its payload's SHAPE and not just its meaning, a reader can
measure a field it has never heard of — and therefore step over it, and
therefore keep it.  That one property is:

- why `pbread` can walk a message with no schema at all;
- why `pbunknown` exists, and why every reader here fills one;
- why `pbdyn` can decode against a descriptor fetched thirty
  milliseconds ago;
- why protobuf's compatibility story is true rather than aspirational.

The failure it prevents is specific and quiet.  A service built against
version 3 of a `.proto` file reads a version 4 message, changes one
field and writes it back; if it dropped the fields it did not know, the
version 4 service at the far end sees them disappear.  Nothing logs it.
Nobody notices until a field that was set is not.

## Which of proto2 and proto3 are in

"Supports proto3" is not a claim anyone can check, so here is the one
that is.

**proto3, whole.**  Singular fields with implicit presence, `optional`
with explicit presence (the synthetic-oneof `proto3_optional` flag),
packed repeated by default, open enums, maps, oneofs, `reserved`.

**proto2 on the wire, whole.**  Groups (wire types 3 and 4, read and
written), `required`, explicit presence, unpacked repeated by default,
closed enums, extension ranges read as ranges.  Every proto2 message
can be read and written by this package.

**proto2 in the generator, partly.**  `pbgen` will not generate for a
file that declares extensions.  An extension is a field declared
outside the message that carries it, which needs a registry the
generated code consults at run time; that is a design decision of its
own and not a line of code.  `pbgen.refusals` names it, and `pbdyn`
reads such a message today.

**Editions are not in.**  A file whose `syntax` is `"editions"` is
`PbUnknownSyntax`.  Feature resolution is a specification of its own,
it changes what every field's presence and packing mean, and guessing
at it would produce a generator whose output is wrong in a way nothing
shows.

## The generated-code contract

This is what `pbgen` will emit, decided here — in `pub` functions a
test can pin — before a line of the generator exists.  Generated code
is an API that a hundred other files depend on, and changing it later
is a migration rather than a patch.

Given

```proto
syntax = "proto3";
package acme.orders;

message Order {
  string id = 1;
  optional int32 quantity = 2;
  repeated sint64 line_totals = 3;
  map<string, string> tags = 4;
  oneof payment { string card = 5; string invoice = 6; }
}
```

the generator writes `acme_orders_order.nv` holding

```novo norun:pseudo
struct AcmeOrdersOrder
    id: Str
    quantity: ?Int
    line_totals: [Int]
    tags: [AcmeOrdersOrderTagsEntry]
    payment: ?AcmeOrdersOrderPayment
    unknown: PbUnknownSet

struct AcmeOrdersOrderTagsEntry
    key: Str
    value: Str

enum AcmeOrdersOrderPayment
    AcmeOrdersOrderPaymentCard(v: Str)
    AcmeOrdersOrderPaymentInvoice(v: Str)

fn encode_acme_orders_order(m: AcmeOrdersOrder) -> Result<Bytes, PbEncodeError>
fn encoded_len_acme_orders_order(m: AcmeOrdersOrder) -> Int
fn decode_acme_orders_order(src: Bytes) -> Result<AcmeOrdersOrder, PbDecodeError>
```

The seven rules behind that, each a function so that a golden file is
not the only thing keeping them:

**Names carry the `.proto` package** — `novo_type_name`.  novo-lang
keys struct identity by NAME across the whole assembly, dependencies
included, so two generated trees that both declared `Order` could not be
used by one program (`docs/publishing.md` § Public type names are
globally unique).  The `.proto` package is the disambiguator the author
already chose, so it is the one to fold in.  The same rule applies to
enum VARIANTS, which are resolved by name too, and to module names.

**A oneof is an enum, and the field is optional** —
`novo_oneof_type_name`.  A oneof with nothing set is the ordinary
state, so the struct holds `?AcmeOrdersOrderPayment`.  proto3's
`optional` keyword produces a SYNTHETIC oneof in the descriptor, and
the generator must not emit that one as a user-visible enum — it emits
`?Int` for the field instead.

**A map is a list of pairs** — `novo_map_entry_type_name`.  Not a
dictionary type: protobuf's map is repeated key-value entries on the
wire, the order is the order the bytes arrived in, duplicate keys are
possible in a message a non-conforming writer produced, and a
dictionary would quietly decide what to do about all three.  A list of
pairs decides nothing, and a caller that wants a dictionary builds one
knowing what it costs.

**Presence is `?T` and implicit presence is `T`** — `has_presence`.  A
proto3 singular scalar cannot tell zero from absent, because they are
the same bytes.  A generator that emitted `?Int` for one would be
claiming information the wire does not carry.

**Eight integral types become one `Int`** — `novo_scalar_type`.
novo-lang has one integer type and it is sixty-four bits signed.  What
that costs is in the limits below.

**Every struct has an `unknown` field** — `unknown_field_name`.  The
generated encoder writes it last.  There is no option to leave it out.

**Reserved words take a trailing underscore** — `novo_field_name`.
`then`, `loop` and `register` are the ones a real `.proto` file meets.

## The layer, and why

`core`.  Everything here is arithmetic over bytes the caller already
holds, and no function declares an effect.  A descriptor set arrives as
bytes the host read; a generated file leaves as text the host writes;
nothing here opens anything.

`pbread.drain` is the one generic function, and it is `[e]` rather than
`[io]`: it binds the source's effect parameter and is charged whatever
the caller's source costs — nothing for a buffer, `[io]` for a socket
(`docs/publishing.md` § How a `core` package takes a stream from its
host).

## No device claim, and why not

This package does **not** carry `tests/embedded_probe.nv`, and the
reason is a dependency rather than a shortcoming.

Every varint on this wire is leb128-nv's — protobuf's varint IS LEB128,
so a second copy inside this package would be a second copy of a
published package rather than a port of anything.  leb128-nv's surface
is `Cursor`- and `Bytes`-shaped, and neither links at
`@tier(embedded)`; the shard audit's `core-embedded` row builds a probe
from the package's own modules and its PATH dependencies' only, so a
registry dependency's sources are not there to copy either way.  A
probe would therefore mean writing a byte-at-a-time varint here, in
parallel with the one this package depends on, for the sake of a claim.

**cbor-nv is the binary encoding the embedded tier has**, and it says so
in its own README: a head codec that allocates nothing, builds for a
Cortex-M4, and lets a sensor write an array head and a few integer
heads without ever building a tree.  A device choosing a wire format
should choose that one.

What would change the answer is an integer-only device half inside
leb128-nv — a `leb128_core` that takes and returns `Int` and holds a
byte-at-a-time scan, the way `base64-nv` splits `base64_core` off
`base64` and `bech32-nv` splits `bech32_core` off `bech32`.  That is a
change to leb128-nv rather than to this package, and it is recorded here
because the lane that makes it should know this is one of its
consumers.

## What is not here

**A `.proto` text parser.**  The text grammar is nearly the whole of
protobuf's surface — import paths, nested option syntax, custom options
that are themselves extensions, editions, reserved statements, three
kinds of comment with a documented attachment rule — and none of it
appears on the wire.  A package that did both would be two packages
sharing a name, and the half that matters for reading bytes would carry
the half that does not.  Descriptors come from `protoc
--descriptor_set_out` or from a gRPC reflection service, and a
descriptor set is itself a protobuf message, so reading one needs
nothing but `pbread`.

**The JSON mapping.**  A separate specification with its own field-name
casing, its own base64 rule for `bytes`, its own spellings for the
well-known types and its own rules for what may be omitted.  Doing half
of it would be worse than not claiming it.  `pbdesc.default_json_name`
is here because the generator needs the name; the mapping is not.

**Signature verification, compression, or anything about a connection.**
The framing that carries a message is grpc-codec-nv's.

**Well-known types translated into novo-lang values.**
`pbdesc.is_well_known` names the thirteen so a caller can find them, and
the generator emits them as the ordinary messages they are.  Mapping
`.google.protobuf.Timestamp` onto calendar-nv's civil types would make a
`core` package depend on a calendar and would produce generated code
nobody can match to the `.proto` file line that made it.

## The limits, named

**`uint64` and `fixed64` above 2^63.**  A novo-lang `Int` is sixty-four
bits signed, so those values come back as the same bits read as a
negative number.  Nothing is lost — re-encoding writes the bytes it
read — but printing one without `pbdyn.uint64_text` prints the wrong
number.  `uint64_of_text` is the way back in.

**`float` narrows.**  A novo-lang `Float` is sixty-four bits; a
protobuf `float` field is thirty-two.  The narrowing happens where the
field's declared type asks for it, and `pbwire.write_float_into` names
it so nobody discovers it from a changed value.

**Field order is the caller's.**  Nothing here reorders fields, because
a writer that reordered them would break a caller re-emitting a message
it must not change — the signed-payload case.

## The reference implementation

Protocol Buffers' own "Encoding" page and `descriptor.proto`, with
`prost` (Rust, Apache-2.0) and `protobuf` (Python, BSD-3-Clause) as the
implementations to check against.  Every byte string in
`tests/protobuf_tests.nv` is from the Encoding page's four worked
examples — `08 96 01`, `12 07 testing`, the embedded message, the
packed `[3, 270, 86942]` — or from the zigzag table beside them, so a
reader can check the port against the specification rather than against
this package.

## Status

| function | implemented |
| --- | --- |
| `pberr.decode_offset`, `.schema_path`, the three `message` impls | no |
| `pbwire.wire_code`, `.wire_of_code`, `.wire_for`, `.fixed_width` | no |
| `pbwire.type_code`, `.type_of_code`, `.type_proto_name` | no |
| `pbwire.min_field_number`, `.max_field_number`, `.reserved_first`, `.reserved_last`, `.is_field_number` | no |
| `pbwire.tag`, `.key_of`, `.tag_of_key`, `.key_len`, `.read_tag_at`, `.write_tag_into` | no |
| `pbwire.write_*_into` (nine) | no |
| `pbwire.read_*_at` (ten) | no |
| `pbwire.varint_len`, `.int32_len`, `.sint32_len`, `.sint64_len`, `.field_len` | no |
| `pbwire.int32_to_wire`, `.int32_of_wire` | no |
| `pbwire.is_packable`, `.packed_by_default`, `.packed_element_count`, `.skip_at` | no |
| `pbread.default_limits`, `.strict_limits`, `.reader` | no |
| `pbread.feed`, `.finish`, `.offset`, `.pending_len`, `.depth`, `.at_boundary` | no |
| `pbread.walk`, `.walk_range`, `.unpack`, `.partition`, `.drain` | no |
| `pbunknown.empty`, `.keep`, `.count`, `.fields_of`, `.by_number`, `.has_number` | no |
| `pbunknown.drop_number`, `.merge`, `.encoded_len`, `.write_into` | no |
| `pbwrite.*_field_len` (six) | no |
| `pbwrite.write_*_field` (fourteen) | no |
| `pbwrite.builder`, `.begin`, `.end`, `.put_*` (seven), `.done` | no |
| `pbdesc.parse_file_set`, `.parse_file`, `.write_file_set`, `.validate` | no |
| `pbdesc.find_*` (four), `.field_by_*` (three), `.oneof_fields`, `.all_messages` | no |
| `pbdesc.packed_of`, `.has_presence`, `.is_map_field`, `.map_key_field`, `.map_value_field` | no |
| `pbdesc.syntax_name`, `.syntax_of_name`, `.default_json_name`, `.is_well_known` | no |
| `pbdyn.message`, `.decode`, `.encode`, `.encoded_len`, `.encode_into` | no |
| `pbdyn.get`, `.get_by_name`, `.set`, `.clear`, `.has`, `.set_numbers`, `.which_oneof` | no |
| `pbdyn.merge`, `.type_check`, `.value_kind`, `.uint64_text`, `.uint64_of_text` | no |
| `pbgen.default_options`, `.generate`, `.generate_set`, `.refusals` | no |
| `pbgen.novo_*` (seven naming rules), `.is_reserved_word` | no |
| `pbgen.encode_fn_name`, `.decode_fn_name`, `.len_fn_name`, `.unknown_field_name` | no |
