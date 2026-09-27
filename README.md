# protobuf-nv

Protocol Buffers is the encoding under gRPC and under most
machine-to-machine traffic inside a data centre. A message is a sequence
of fields and nothing else: each one a key, then a payload whose shape
the key announces. The encoding is described on Protocol Buffers'
[Encoding page](https://protobuf.dev/programming-guides/encoding/), and
the schema language's own data structures are in `descriptor.proto`.
This package reads and writes the wire format, reads and writes
descriptor sets, decodes a message by a descriptor read at run time, and
generates novo-lang code for a schema.

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

A **descriptor set** is the binary form of one or more `.proto` files:
the `FileDescriptorSet` message that `protoc --descriptor_set_out`
writes and that a gRPC reflection service serves. It is itself a
protobuf message.

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
use pbread
use pbwrite

fn main() [io]
    // A builder over a buffer it sizes itself, under the default limits.
    let b = pbwrite.builder(pbwrite.build_limits())

    // Field number 1, wire type 0, the varint 150: the Encoding page's
    // first example.
    match pbwrite.put_varint(b, 1, 150)
        Err(e) => println(e.message())
        Ok(b2) =>
            match pbwrite.done(b2)
                Err(e)  => println(e.message())
                Ok(out) =>
                    // 089601
                    println(bytes.to_hex(out))
                    // Read it back: one field, number 1.
                    match pbread.walk(out, pbread.default_limits())
                        Ok(evs) => println("${evs.len()}")
                        Err(e)  => println(e.message())
```

## What the package contains

| Module | Contents |
| --- | --- |
| `pberr` | The three refusals, for decoding, encoding and schemas, with the byte offset or the dotted path each carries. |
| `pbwire` | The encoding itself: keys, the six wire types, the codings of every scalar type, binary32 rounding, the UTF-8 rule, the length arithmetic, and the rule for skipping a field nobody declared. |
| `pbread` | Reading a message: by walking a buffer, or by feeding chunks to a reader that answers fields as they finish. Both take a limits value. |
| `pbunknown` | The fields a reader did not understand, kept as they arrived, so that a message can be written back out unchanged. |
| `pbwrite` | Writing into a buffer the caller owns: the size of each field, the writers, and a builder that closes a nested message when you end it. |
| `pbdesc` | A descriptor set as novo-lang values, read and written, the checks a schema must pass, and the questions a generator asks of one. |
| `pbdyn` | A message addressed by field number against a descriptor, for a program that was not built with the schema. |
| `pbgen` | The code generator, and the naming rules its output follows. |
| `pbcodec` | The typed readers and writers that generated code calls. |

## How to choose an entry point

**`pbread.walk` reads a message you hold.** It answers every field with
its number, its wire type and its payload, whether or not you have a
schema. `pbread.partition` splits the fields into the ones your schema
declares and the ones to keep.

**`pbread.reader` and `feed` read a message that arrives in pieces.**
`finish` says where it ends. `drain` is the loop over a `Read` source.

**`pbwrite` writes one.** Size the message with the `*_len` functions
and write it once, or use the builder: begin a nested message, put its
fields, end it, and the length is written for you.

**`pbgen` is the entry point when you have the schema.** It turns a
descriptor set into novo-lang modules with a struct per message and an
encoder and a decoder for each.

**`pbdyn` is the entry point when the schema arrives at run time.** It
takes a descriptor and addresses fields by number or by name.

**`pbwire` is the entry point for a codec author.** It is the key
arithmetic and the scalar codings with nothing above them.

## The rules a user needs

1. **A message is not self-delimiting.** The format has no end marker.
   The caller's framing or buffer says where a message stops.
2. **Keep the fields you did not understand.** Every reader here keeps
   them in a `PbUnknownSet`, every generated struct has a field for
   them that the encoder writes last, and `pbdyn` keeps them too. A
   service that drops unknown fields makes a newer peer's data
   disappear on every round trip, with nothing logged.
3. **`pbwire.skip_at` is what makes that possible.** A key announces its
   payload's shape, so a field can be measured without being understood.
4. **`int32` and `sint32` are different encodings.** A negative `int32`
   is sign-extended to 64 bits and costs ten bytes. `sint32` and
   `sint64` zigzag fold first.
5. **Repeated numeric fields are packed by default in proto3 and not in
   proto2.** `pbdesc.packed_of` answers which a field is. A reader
   accepts both forms whatever the schema says (Encoding page, section
   "Packed Repeated Fields").
6. **Nothing here reorders fields.** `pbwrite` writes in the caller's
   order and `pbdyn` in the order fields were set. A decoded message
   that nobody changed encodes to the bytes it came from, when those
   bytes were in field-number order.
7. **Field numbers 19000 to 19999 may not be declared.** `pbwrite`
   refuses to write one. A message that arrives carrying one is still
   read.
8. **Limits are a value, and there are two named sets.**
   `pbread.default_limits` is depth 100 and 64 MiB.
   `pbread.strict_limits` is depth 32 and 1 MiB, for messages from
   somewhere untrusted.
9. **`uint64` and `fixed64` above 2^63 come back as negative numbers.**
   A novo-lang `Int` is signed and 64 bits. Nothing is lost, because
   encoding writes the same bits, but printing one needs
   `pbdyn.uint64_text`, and `pbdyn.uint64_of_text` is the way back.
10. **A protobuf `float` is 32 bits and a novo-lang `Float` is 64.**
    Writing a `float` rounds to the nearest binary32, ties to even (IEEE
    754 section 4.3.1). Reading one widens it exactly.
11. **A proto3 singular scalar cannot tell zero from absent.** They are
    the same bytes. `pbdesc.has_presence` answers which fields carry
    presence. Generated code holds those as `?T`, and `pbdyn` does not
    set a field without presence that arrives as its zero.
12. **A map is repeated key-value entries.** The order is the order the
    bytes arrived in, and a key may repeat in a message a
    non-conforming writer produced. Generated code holds a list of
    entry structs, so a caller that wants a dictionary builds one.
13. **A singular submessage that arrives twice is merged.** The
    specification defines two occurrences as the merge of the two,
    which is what decoding their concatenation gives. `pbdyn` and
    generated code both do this. A oneof keeps its last member.

## The code the generator writes

For `.acme.Order` in `acme/order.proto`, `pbgen.generate_set` writes a
module `acme_order` holding:

| Item | Name |
| --- | --- |
| The struct, with a `var` field per field and a last field `unknown` | `AcmeOrder` |
| The message with every field at its default | `new_acme_order()` |
| The size of the encoding | `encoded_len_acme_order(m)` |
| The encoding written at a cursor | `write_acme_order(m, dst)` |
| The encoding as a new buffer | `encode_acme_order(m)` |
| The message read back | `decode_acme_order(src, limits)` |
| A oneof `payment`, held as an optional | `AcmeOrderPayment`, with a variant per member |
| A map field `tags` | a list of `AcmeOrderTagsEntry`, with fields `key` and `value` |
| An enum `.acme.Currency` | `AcmeCurrency`, `acme_currency_number`, `acme_currency_of` |
| A service `.acme.Orders` | a module `acme_order_orders` answering each method's gRPC path |

A name carries the `.proto` package, because novo-lang resolves a struct
or a variant by its name across the whole program and two generated
trees that both declared `Order` could not be used together. A field
whose name is a novo-lang reserved word takes a trailing underscore.
An enum field is an `Int` holding the value's number, because proto3
enums are open and a number the schema does not name must survive a
round trip. The functions in `pbgen` named `novo_*` and `*_fn_name` are
these rules, so a test or a second generator can apply them.

`pbgen.refusals` names what the generator does not produce: an
extension, which needs a registry the generated code would consult at
run time; a group, which `pbdyn` reads instead; a file declaring an
edition; and two generated names that would be the same.

## What this reads, and what it does not

**proto3, whole.** Singular fields with implicit presence, `optional`
with explicit presence, packed repeated fields by default, open enums,
maps, oneofs and `reserved`.

**proto2, whole on the wire and in `pbdyn`.** Groups, `required`,
explicit presence, unpacked repeated fields by default, closed enums,
and extensions, which a decoder keeps as unknown fields. The generator
refuses a file that declares a group or an extension.

**Editions are carried and not interpreted.** A file whose syntax is
`"editions"` reads as `PbSyntaxOther`, `pbdesc.validate` reports it, and
the generator refuses it. Feature resolution is a specification of its
own that changes what every field's presence and packing mean.

## What is not included

- **A `.proto` text parser.** The text grammar is nearly the whole of
  protobuf's surface and none of it appears on the wire. Descriptors
  come from `protoc --descriptor_set_out` or from a gRPC reflection
  service.
- **The JSON mapping.** It is a separate specification with its own
  field-name casing, its own base64 rule for byte fields and its own
  spellings for the well-known types. `pbdesc.default_json_name` is here
  because a descriptor needs the name; the mapping is not.
- **The well-known types as novo-lang values.** `pbdesc.is_well_known`
  names them, and the generator emits them as the ordinary messages
  they are.
- **The descriptor fields no program here uses.** A field's and a
  oneof's other options, an enum's reserved ranges, `weak_dependency`,
  `source_code_info` and `edition` are dropped on reading. The other
  options of a file, a message, an enum, a service and a method are
  kept whole and written back.
- **Connections, framing and compression.** The framing that carries a
  message is
  [grpc-codec-nv](https://novo-lang.org/packages/grpc-codec-nv)'s.
- **A build for a microcontroller.** Every varint here is
  [leb128-nv](https://novo-lang.org/packages/leb128-nv)'s, and that
  package's surface takes `Bytes` and `Cursor`, neither of which links
  on a device.
  [cbor-nv](https://novo-lang.org/packages/cbor-nv) is the binary format
  with a device half.
- **Any input or output.** A descriptor set arrives as bytes the host
  read, and a generated file leaves as text the host writes.

## Related packages

- [leb128-nv](https://novo-lang.org/packages/leb128-nv),
  [zigzag-nv](https://novo-lang.org/packages/zigzag-nv) and
  [varint-nv](https://novo-lang.org/packages/varint-nv) are the
  dependencies. Protobuf's varint is LEB128, and its `sint` types are
  that with a zigzag fold.
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
for s in tests/*_tests.nv; do novo test "$s"; done   # 206 tests
bash tests/coverage.sh                               # line coverage over src/
python3 tools/roundtrip.py                           # needs protobuf and grpcio-tools
```

The reference data comes from three places. The Encoding page's worked
examples, `08 96 01`, `12 07 testing`, the embedded message and the
packed `[3, 270, 86942]`, are in `protobuf_tests.nv`. `oracle_tests.nv`
holds descriptor sets `protoc` wrote for `tests/proto` and messages
Google's protobuf module serialised from them, written there by
`tools/vectors.py`: a set read here and written back is `protoc`'s own
bytes, and a message decoded by `pbdyn` and encoded again is Python's
own bytes. `tools/roundtrip.py` generates code for `tests/proto`,
checks that `novo fmt` leaves it unchanged, builds it, decodes and
re-encodes Python's messages byte for byte, and has Python read a
message the generated code wrote.

The other suites cover every refusal with its offset, binary32 rounding
at its edges, RFC 3629's UTF-8 cases, the reader fed in chunks,
`validate`'s every finding, and the generator's naming rules and
refusals.

## Licence

Apache-2.0. See `LICENSE`.
