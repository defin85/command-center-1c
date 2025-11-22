# RAS Client (Vendored Copy)

This is a vendored copy of the [khorevaa/ras-client](https://github.com/khorevaa/ras-client) library.

**Original Repository:** https://github.com/khorevaa/ras-client
**License:** See LICENSE file
**Reason for vendoring:** Custom modifications to fix empty string encoding in protocol/codec/encoder.go

## Modifications

- **protocol/codec/encoder.go**: Changed empty string encoding from NULL (0x00) to UTF-8 replacement char (0x03 0xef 0xbf 0xbd) to match rac.exe behavior and prevent RAS from attempting PostgreSQL validation on metadata-only operations (Lock/Unlock).

## Sync

To update from upstream:
```bash
cd /tmp
git clone https://github.com/khorevaa/ras-client.git
cd ras-client
# Manually merge changes, preserving our modifications
```
