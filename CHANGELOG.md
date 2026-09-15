# Changelog

Every published version, newest first. This file is on the publish
allow-list, so it travels with the package: it is the only thing a
consumer deciding whether to upgrade can read.

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
