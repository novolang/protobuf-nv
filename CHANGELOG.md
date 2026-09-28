# Changelog

Every published version, newest first. This file is on the publish
allow-list, so it travels with the package: it is the only thing a
consumer deciding whether to upgrade can read.

## 0.1.0 — 2026-09-27

The first implementation of the interface published as 0.0.1: the
wire format, the reader and the writers, descriptor sets, the dynamic
message and the code generator.

### Behaviour the interface left open

- A key's wire type is checked on its first byte, so `0xff` alone is
  `PbUnknownWireType` rather than a truncated varint.
- `PbVarintOverflow.bytes` is the length of the run of continuation
  bytes, including the byte that ends it.
- The reader waits, under `feed`, for a length-delimited field that has
  not finished, and refuses it as `PbLengthOverrun` at `finish` and in
  `walk`.  A length that would pass the byte limit is
  `PbMessageTooLarge` as soon as it arrives.
- `pbwire.field_len` of a group counts the end key too.
- `pbwrite.write_packed_field`, `put_fixed` and `put_packed` take the
  IEEE 754 bit pattern for `float` and `double` elements.
- The builder answers `PbBufferTooSmall` with its byte limit as `left`
  when a level would pass it.
- `pbdyn.set` does not clear a oneof's other members, having no
  descriptor; `decode` keeps a oneof's last member.  A singular
  submessage that arrives twice is merged, and a proto3 scalar without
  presence that arrives as zero is not set.  `encoded_len` encodes to
  count.
- `pbdesc.parse_file_set` keeps the unnamed options of files,
  messages, enums, services and methods, and `write_file_set` writes
  them back in field-number order; a set read and written again is
  `protoc`'s own bytes.

### Changes to the interface

- `PbDecodeError` gains `PbTransport(at, cause: IoError)`, for a
  source that fails under `pbread.drain`.
- `PbEncodeError` gains `PbSchemaRefused(error)`, which `pbdyn.encode`
  answers for a value that does not fit its descriptor.
- `PbSchemaError` gains `PbUndeclaredField`, `PbKindMismatch` and
  `PbNotGenerated`.
- `PbSyntax` gains `PbSyntaxOther(name)`, so a file declaring an
  edition reads and is reported rather than misread as proto2.
- `PbField` gains `extendee`, and `PbFile` and `PbMessage` gain
  `extensions`, so an extension is read, written back and refused by
  the generator.
- `PbGenOptions` loses `serde_impls` and `carry_comments`.  Every
  struct and enum already implements `Serialize` and `Deserialize`
  (SPEC section 3.8.1), and a descriptor set carries comments only in
  `source_code_info`, which this package does not read.
- `PbGenerated.path` is flat, the module name and `.nv`, because a
  novo-lang module is found by its file name.
- An enum field generates as an `Int`, so a number the schema does not
  name survives a round trip.
- New: `pberr.shifted`; `pbwire.float32_bits`, `float_of_bits32`,
  `first_non_utf8`, `delimited_at` and `PbSpan`; `pbread.bits_of` and
  `data_of`; `pbdesc.file_of` and `has_extensions`; `pbgen`'s
  `write_fn_name`, `new_fn_name`, `enum_number_fn_name`,
  `enum_of_fn_name`, `novo_oneof_variant_name`, `method_path`,
  `method_path_fn_name` and `descriptor_fn_name`; and the module
  `pbcodec`, the calls generated code makes.

### Dependencies and toolchain

- leb128-nv `^0.1.7`, zigzag-nv `^0.1.5` and varint-nv `^0.1.6`, the
  first releases of each that build with novo 0.11 and later.
- The toolchain floor is 0.14.0.  The bodies target novo 0.14.0 and
  carry no workaround for a compiler defect.

### Tests

- 206 tests in nine suites, with 100% line coverage over `src/`
  measured by `tests/coverage.sh`.
- `oracle_tests.nv` holds descriptor sets from `protoc` and messages
  from Google's protobuf module, written by `tools/vectors.py`.
- `tools/roundtrip.py` builds generated code and checks it against
  Google's protobuf module in both directions and against `novo fmt`.

## 0.0.3 — 2026-09-25

The package builds with novo 0.11.  Every body is still `todo()`.

- The lock file moves leb128-nv 0.1.5 to 0.1.7, varint-nv 0.1.4 to 0.1.6
  and zigzag-nv 0.1.4 to 0.1.5.  leb128-nv 0.1.5 and varint-nv 0.1.4
  write into lists through names that are not declared `var`, which novo
  0.11 refuses (E2038), so this package did not build with novo 0.11
  against them.  No requirement in the manifest changed.
- A `mut` parameter is written `var`, the spelling `novo fmt` writes.
  The two spellings mean the same thing, and no signature changed.

## 0.0.2 — 2026-09-15

README rewritten to the package README style guide (docs/writing-a-readme.md); no change to the interface.

## 0.0.1 — 2026-09-11

The **interface**, before anyone implements it.  Every signature, every
type and every effect row is published; every body is `todo()`, and the
release is stamped `NOT IMPLEMENTED — interface only`.  Adding this
package works and calling it panics.

- Seven modules.  `pbwire` is the encoding itself — keys, the six wire
  types, the eighteen declared types and the rule for skipping a field
  nobody declared; `pbread` is a feed-and-drain reader; `pbwrite` is a
  writer into the caller's buffer with a builder beside it;
  `pbunknown` is the fields a reader did not recognise, kept whole;
  `pbdesc` is `FileDescriptorProto` as novo-lang values; `pbdyn` is a
  message addressed by field number; `pbgen` is the code generator's
  contract.
- **`pbwire.skip_at` is the load-bearing interface.**  A key announces
  its payload's shape, so a reader can measure a field it has never
  heard of — and therefore step over it, and therefore keep it.  Every
  other decision here follows from that one.
- **Every reader fills a `PbUnknownSet`, and there is no option to turn
  it off.**  A service that drops a newer peer's fields loses data that
  nothing logs; the raw bytes are kept, key included, in arrival order,
  and written back last.
- **The generated-code contract is published as functions, not as
  prose.**  `novo_type_name`, `novo_field_name`, `novo_variant_name`,
  `novo_oneof_type_name`, `novo_map_entry_type_name`,
  `novo_module_name` and `novo_scalar_type` are `pub` so that a test
  can pin the rule and a second generator — grpc-codec-nv's service
  stubs — has something to agree with.  A oneof is an enum, a map is a
  list of pairs, presence is `?T`, and a generated name carries the
  `.proto` package because novo-lang keys struct identity by name
  across the whole assembly.
- **What is in, precisely.**  proto3 whole; proto2 whole on the wire,
  groups included; proto2 partly in the generator, which refuses a file
  that declares extensions; editions not at all, because feature
  resolution changes what every field's presence means and guessing at
  it produces output that is wrong in a way nothing shows.
- **No `.proto` text parser**, and the README says why: the text
  grammar is nearly the whole of protobuf's surface and none of it
  appears on the wire.  Descriptors arrive as a binary
  `FileDescriptorSet`, which is itself a protobuf message.
- **No device claim**, and the README says why that is a dependency
  rather than a shortcoming: every varint here is leb128-nv's, that
  package's surface is `Cursor`-shaped, and a probe would mean a second
  varint in this package.  cbor-nv is the binary encoding the embedded
  tier has.
- The vectors are the Encoding page's own four worked examples —
  `08 96 01`, `12 07 testing`, the embedded message, the packed
  `[3, 270, 86942]` — and the zigzag table beside them.
