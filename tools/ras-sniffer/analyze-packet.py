#!/usr/bin/env python3
# Analyze RAS UpdateInfobase request for db_pwd field

packet11_hex = """
01 00 00 01 28 c3 e5 08  59 3d 41 43 83 b0 d7 4e
e2 02 72 b6 9d 5b 1b a2  60 a8 23 40 b7 86 88 aa
17 d2 75 47 7b 00 00 00  00 0a 50 6f 73 74 67 72
65 53 51 4c 04 74 65 73  74 03 ef bf bd 09 6c 6f
63 61 6c 68 6f 73 74 08  70 6f 73 74 67 72 65 73
00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00
00 00 00 05 72 75 5f 52  55 04 74 65 73 74 00 01
00 00 00 00 00 00 00 00  01 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00  00 00 00
"""

# Convert hex string to bytes
hex_bytes = bytes.fromhex(packet11_hex.replace('\n', ''))

print("Total packet length:", len(hex_bytes), "bytes")
print("\nField offsets:")
print("Offset 0x025-0x028: DateOffset")
print("Offset 0x029-0x033: DBMS =", hex_bytes[0x029:0x034].decode('utf-8', errors='ignore'))
print("Offset 0x034-0x038: DBName =", hex_bytes[0x034:0x039].decode('utf-8', errors='ignore'))

# DBPwd field starts after DBName
print("\nOffset 0x039: DBPwd length byte =", hex(hex_bytes[0x039]))
print("Offset 0x03A-: DBPwd value =", hex_bytes[0x03A:0x03A+10].hex())

# If length is 0x03, then we have 3 bytes of UTF-8 replacement char (ef bf bd)
if hex_bytes[0x039] == 0x03:
    print("\nDB Password field: 3 bytes = UTF-8 replacement char (U+FFFD)")
    print("This represents an EMPTY or INVALID string, NOT a real password")
else:
    print(f"\nDB Password length: {hex_bytes[0x039]} bytes")

print("\nOffset 0x03D: DBServer length byte =", hex(hex_bytes[0x03D]))
print("Offset 0x03E-: DBServer =", hex_bytes[0x03E:0x03E+9].decode('utf-8', errors='ignore'))

print("\nOffset 0x047: DBUser length byte =", hex(hex_bytes[0x047]))
print("Offset 0x048-: DBUser =", hex_bytes[0x048:0x048+8].decode('utf-8', errors='ignore'))
