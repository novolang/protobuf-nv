# protobuf-nv

Protocol Buffers is the encoding under gRPC and under most
machine-to-machine traffic inside a data centre. A message is a sequence
of fields and nothing else: each one a key, then a payload whose shape
the key announces. The encoding is described on Protocol Buffers'
[Encoding page](https://protobuf.dev/programming-guides/encoding/), and
the schema language's own data structures are in `descriptor.proto`.
This package reads and writes the wire format, reads descriptors, and
states the contract its code generator will emit.

**Status: NOT IMPLEMENTED — interface only.** Every function is declared
with its full signature, but every body is a `todo()` that panics when
called. The package is published so its design can be reviewed and
depended on before it is implemented. Version 0.1.0 will be the first
working release.

## What the wire format is

A **field** is a **key** and then a payload. The key is a varint whose
low three bits are the **wire type** and whose remaining bits are the
**field number**. A **varint** is an integer written seven bits per
byte, least significant first, with the top bit set while more bytes
follow. That is LEB128.

There are six wire types. Type 0 is a varint payload. Type 1 is eight
fixed bytes and type 5 is four. Type 2 is a length-delimited run: a
varint length and then that many bytes, which is how strings, byte runs
and nested messages travel. Types 3 and 4 open and close a **group**,
which is proto2's older way of nesting and is still on the wire in a
great deal of deployed software. Codes 6 and 7 are not defined.

A message has no header, no length, no field count and no end marker.
Something outside the format always says where a message stops: a
length prefix, a frame, or the end of the buffer.

Because the shape travels with the key, a reader can measure a field it
has never heard of. It can therefore skip it, and it can therefore keep
it. That is what makes it safe to add a field to a schema, and it is
what **unknown field preservation** means: a reader keeps the fields it
did not understand and writes them back out.

Signed integers have two encodings. An `int32` or `int64` is written as
its two's complement, so a negative number is sign-extended and costs
ten bytes. A `sint32` or `sint64` is **zigzag folded** first, so a small
negative number stays small. Repeated numeric fields may be **packed**:
one length-delimited field holding the values end to end.

| Quantity | Value |
| --- | --- |
| Wire type of a varint | 0 |
| Wire types of fixed payloads | 1 (8 bytes), 5 (4 bytes) |
| Wire type of a length-delimited run | 2 |
| Wire types of a group | 3 and 4 |
| Lowest field number | 1 |
| Highest field number | 536870911 |
| Field numbers reserved by the descriptor language | 19000 to 19999 |
| Default nesting limit | 100 |
| Default limit on one message | 64 MiB |
| Strict limits | depth 32, 1 MiB |
| Bytes a negative `int32` costs | 10 |

## Install

```
novo pkg add protobuf-nv
```

## Example

```novo
use std.bytes
use pbwrite

fn main() [io]
    // A builder over a buffer it sizes itself, under the default limits.
    let b = pbwrite.builder(pbwrite.build_limits())

    // Field number 1, wire type 0, the varint 150. This is the
    // Encoding page's own first example.
    match pbwrite.put_varint(b, 1, 150)
        Err(e) => println(e.message())
        Ok(b2) =>
            match pbwrite.done(b2)
                // 089601
                Ok(out) => println(bytes.to_hex(out))
                Err(e)  => println(e.message())
```

Build and test with `novo pkg build` and `novo test`. Today `novo test`
fails on purpose: every test reaches a `not implemented: <module>.<fn>`
panic. The tests are the specification the implementation will have to
satisfy.

## What the package contains

| Module | Contents |
| --- | --- |
| `pberr` | The three refusals — decoding, encoding and schema — with the offset or the schema path each carries. |
| `pbwire` | The encoding itself: keys, the six wire types, the codings of every scalar type, the length arithmetic, and the rule for skipping a field nobody declared. |
| `pbread` | Reading a message: by walking a buffer, or by feeding chunks to a reader that answers fields as they finish. Both take a limits value. |
| `pbunknown` | The fields a reader did not understand, kept as they arrived, so that a message can be written back out unchanged. |
| `pbwrite` | Writing into a buffer the caller owns: the size of each field, the writers, and a builder that closes a nested message when you end it. |
| `pbdesc` | A `FileDescriptorSet` as novo-lang values: the messages, fields, enums and oneofs a schema declares, and the questions a generator asks of them. |
| `pbdyn` | A message addressed by field number against a descriptor, for a program that never had a `.proto` file. |
| `pbgen` | The code generator's contract: the naming rules, the function names, and what it refuses. |

## How to choose an entry point

**`pbread.walk` reads a message you hold.** It answers every field with
its number, its wire type and its payload, whether or not you have a
schema.

**`pbread.reader` and `feed` read a message that arrives in pieces.**

**`pbwrite.builder` writes one.** Begin a nested message, put its
fields, end it, and the lengths are back-filled.

**`pbdyn` is the entry point when the schema arrived at run time.** It
takes a descriptor and addresses fields by number or by name.

**`pbwire` is the entry point for a codec author.** It is the key
arithmetic and the scalar codings with nothing above them.

## The rules a user needs

1. **A message is not self-delimiting.** The format has no end marker.
   The caller's framing or buffer says where a message stops.
2. **Keep the fields you did not understand.** Every reader here fills a
   `PbUnknownSet`, and every generated struct has a field for it that
   the encoder writes last. A service that drops unknown fields makes a
   newer peer's data disappear on every round trip, with nothing logged.
3. **`pbwire.skip_at` is what makes that possible.** A key announces its
   payload's shape, so a field can be measured without being understood.
4. **`int32` and `sint32` are different encodings.** A negative `int32`
   is sign-extended to 64 bits and costs ten bytes. `sint32` and
   `sint64` zigzag fold first. `pbwire.int32_to_wire` is that sign
   extension named.
5. **Repeated numeric fields are packed by default in proto3 and not in
   proto2.** `pbdesc.packed_of` answers which a field is. A reader
   accepts both forms whatever the schema says.
6. **Nothing here reorders fields.** A caller re-emitting a message it
   must not change — one carrying a signature, for instance — depends on
   that.
7. **Field numbers 19000 to 19999 may not be declared.** `pbwrite`
   refuses to write one. A message that arrives carrying one is still
   read, because a peer's mistake is not a reason to drop a message.
8. **Limits are a value, and there are two named sets.**
   `pbread.default_limits` is depth 100 and 64 MiB.
   `pbread.strict_limits` is depth 32 and 1 MiB, for messages from
   somewhere untrusted.
9. **`uint64` and `fixed64` above 2^63 come back as negative numbers.**
   A novo-lang `Int` is signed and 64 bits. Nothing is lost, because
   re-encoding writes the bytes it read, but printing one needs
   `pbdyn.uint64_text`, and `pbdyn.uint64_of_text` is the way back.
10. **A protobuf `float` field is 32 bits and a novo-lang `Float` is
    64.** The narrowing happens where the field's declared type asks for
    it. `pbwire.write_float_into` is where it is named.
11. **A proto3 singular scalar cannot tell zero from absent.** They are
    the same bytes. `pbdesc.has_presence` answers which fields carry
    presence, and the generator emits `?T` only for those.
12. **A map is repeated key-value entries.** Duplicate keys are possible
    in a message a non-conforming writer produced, and the order is the
    order the bytes arrived in. The generator emits a list of pairs, so
    a caller that wants a dictionary builds one knowing what it costs.
13. **A proto3 `optional` field is a synthetic oneof in the
    descriptor.** A generator must not emit it as a user-visible enum.
14. **Generated type names carry the `.proto` package.** novo-lang
    resolves struct and enum variant names across the whole assembly, so
    two generated trees that both declared `Order` could not be used by
    one program.

## What this reads, and what it does not

**proto3, whole.** Singular fields with implicit presence, `optional`
with explicit presence, packed repeated by default, open enums, maps,
oneofs and `reserved`.

**proto2 on the wire, whole.** Groups, `required`, explicit presence,
unpacked repeated by default, closed enums, and extension ranges read as
ranges. Every proto2 message can be read and written here.

**proto2 in the generator, partly.** `pbgen` refuses a file that
declares extensions. An extension is a field declared outside the
message that carries it, and it needs a registry the generated code
consults at run time. `pbgen.refusals` names the refusal, and `pbdyn`
reads such a message today.

**Editions are not read.** A file whose syntax is `"editions"` is
`PbUnknownSyntax`. Feature resolution is a specification of its own and
it changes what every field's presence and packing mean.

## What is not included

- **A `.proto` text parser.** The text grammar is nearly the whole of
  protobuf's surface and none of it appears on the wire. Descriptors
  come from `protoc --descriptor_set_out` or from a gRPC reflection
  service, and a descriptor set is itself a protobuf message, so reading
  one needs only `pbread`.
- **The JSON mapping.** A separate specification with its own field-name
  casing, its own base64 rule for byte fields and its own spellings for
  the well-known types. `pbdesc.default_json_name` is here because the
  generator needs the name; the mapping is not.
- **The well-known types as novo-lang values.**
  `pbdesc.is_well_known` names the thirteen, and the generator emits
  them as the ordinary messages they are. Mapping
  `.google.protobuf.Timestamp` onto a calendar type would make this
  package depend on a calendar and would produce generated code nobody
  can match to the line that made it.
- **Connections, framing and compression.** The framing that carries a
  message is
  [grpc-codec-nv](https://novo-lang.org/packages/grpc-codec-nv)'s.
- **A build for a microcontroller.** Every varint here is
  [leb128-nv](https://novo-lang.org/packages/leb128-nv)'s, and that
  package's surface takes `Bytes` and `Cursor`, neither of which links
  on a device. Writing a second byte-at-a-time varint here for the sake
  of a claim would be a second copy of a published encoding. An
  integer-only half inside leb128-nv would change the answer, and that
  is a change to leb128-nv.
  [cbor-nv](https://novo-lang.org/packages/cbor-nv) is the binary format
  with a device half today.
- **Any input or output.** A descriptor set arrives as bytes the host
  read, and a generated file leaves as text the host writes.

## Related packages

- [leb128-nv](https://novo-lang.org/packages/leb128-nv),
  [zigzag-nv](https://novo-lang.org/packages/zigzag-nv) and
  [varint-nv](https://novo-lang.org/packages/varint-nv) are the
  dependencies. Protobuf's varint is LEB128, its `sint` types are that
  with a zigzag fold, and writing them again here would be copies to
  keep in step.
- [grpc-codec-nv](https://novo-lang.org/packages/grpc-codec-nv) is the
  framing and the header rules gRPC puts around these messages.
- [cbor-nv](https://novo-lang.org/packages/cbor-nv) and
  [msgpack-nv](https://novo-lang.org/packages/msgpack-nv) are
  self-describing: a reader needs no schema at all, and the documents
  are larger.
- [postcard-nv](https://novo-lang.org/packages/postcard-nv) goes the
  other way: no tags at all, so both ends must agree exactly and a
  reader can skip nothing.
- [asn1-nv](https://novo-lang.org/packages/asn1-nv) is the other
  tag-length-value format on the registry, with a canonical form
  protobuf does not have.

## Tests

```bash
novo test tests/protobuf_tests.nv      # 74 tests
```

Every byte string is from the Encoding page's worked examples — `08 96
01`, `12 07 testing`, the embedded message and the packed
`[3, 270, 86942]` — or from the zigzag table beside them. The
descriptor structures are `descriptor.proto`'s own. The implementations
to check a port against are `prost` in Rust and `protobuf` in Python.

The suite asserts that a key packs a field number and a wire type, that
each scalar coding round-trips, that a negative `int32` costs ten bytes
and a `sint32` does not, that a field of an unknown number is measured
and kept, that a kept field is written back byte for byte, that packed
and unpacked repeated fields both read, that nesting past the limit is
refused, that a message larger than the limit is refused before anything
is reserved for it, that a reserved field number is refused on write and
accepted on read, that the descriptor questions answer what the schema
says, and that each of the generator's naming rules produces the name
the contract above states.

The tests compile today and fail at run, each on the `not implemented`
panic that is its body. That is the expected state of an interface
release. They turn green one at a time as bodies land.

## Implementation status

| Item | Implemented |
| --- | --- |
| `pberr.decode_offset`, `.schema_path`, the three `message` impls | no |
| `pbwire.wire_code`, `.wire_of_code`, `.wire_for`, `.fixed_width` | no |
| `pbwire.type_code`, `.type_of_code`, `.type_proto_name` | no |
| `pbwire.min_field_number`, `.max_field_number`, `.reserved_first`, `.reserved_last`, `.is_field_number` | no |
| `pbwire.tag`, `.key_of`, `.tag_of_key`, `.key_len`, `.read_tag_at`, `.write_tag_into` | no |
| `pbwire.write_*_into`, nine writers | no |
| `pbwire.read_*_at`, ten readers | no |
| `pbwire.varint_len`, `.int32_len`, `.sint32_len`, `.sint64_len`, `.field_len` | no |
| `pbwire.int32_to_wire`, `.int32_of_wire` | no |
| `pbwire.is_packable`, `.packed_by_default`, `.packed_element_count`, `.skip_at` | no |
| `pbread.default_limits`, `.strict_limits`, `.reader` | no |
| `pbread.feed`, `.finish`, `.offset`, `.pending_len`, `.depth`, `.at_boundary` | no |
| `pbread.walk`, `.walk_range`, `.unpack`, `.partition`, `.drain` | no |
| `pbunknown.empty`, `.keep`, `.count`, `.fields_of`, `.by_number`, `.has_number` | no |
| `pbunknown.drop_number`, `.merge`, `.encoded_len`, `.write_into` | no |
| `pbwrite.*_field_len`, six functions | no |
| `pbwrite.write_*_field`, fourteen functions | no |
| `pbwrite.builder`, `.begin`, `.end`, `.put_*`, `.done` | no |
| `pbdesc.parse_file_set`, `.parse_file`, `.write_file_set`, `.validate` | no |
| `pbdesc.find_*`, `.field_by_*`, `.oneof_fields`, `.all_messages` | no |
| `pbdesc.packed_of`, `.has_presence`, `.is_map_field`, `.map_key_field`, `.map_value_field` | no |
| `pbdesc.syntax_name`, `.syntax_of_name`, `.default_json_name`, `.is_well_known` | no |
| `pbdyn.message`, `.decode`, `.encode`, `.encoded_len`, `.encode_into` | no |
| `pbdyn.get`, `.get_by_name`, `.set`, `.clear`, `.has`, `.set_numbers`, `.which_oneof` | no |
| `pbdyn.merge`, `.type_check`, `.value_kind`, `.uint64_text`, `.uint64_of_text` | no |
| `pbgen.default_options`, `.generate`, `.generate_set`, `.refusals` | no |
| `pbgen.novo_*`, the seven naming rules, and `.is_reserved_word` | no |
| `pbgen.encode_fn_name`, `.decode_fn_name`, `.len_fn_name`, `.unknown_field_name` | no |

## Licence

Apache-2.0. See `LICENSE`.

<!-- docs/writing-a-readme.md is the style guide for this page. -->
