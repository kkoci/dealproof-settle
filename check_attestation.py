"""Check an attest-service response against a deal: the TDX quote's report_data must start with deal_hash.

Usage: python check_attestation.py <deal file> <attest response json>
Prints OK or FAILED: <reason>. Exit code 0 only on OK.
Note: this is a binding/consistency check only; it does not verify the quote's
Intel signature chain (use a DCAP verifier / Phala's verification service for that).
"""
import json
import struct
import sys

HEADER = 48           # TDX quote header size
REPORT_DATA_OFF = 520 # offset of REPORTDATA inside the TD 1.0 quote body


def report_data_from_quote(quote: bytes) -> bytes:
    version = struct.unpack_from("<H", quote, 0)[0]
    if version == 4:
        start = HEADER + REPORT_DATA_OFF
    elif version == 5:
        start = HEADER + 6 + REPORT_DATA_OFF  # v5: body type (2) + body size (4)
    else:
        raise ValueError(f"unsupported quote version {version}")
    if len(quote) < start + 64:
        raise ValueError("quote too short")
    return quote[start:start + 64]


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__.strip().splitlines()[2])
        return 2
    try:
        deal = json.load(open(sys.argv[1], encoding="utf-8"))
        resp = json.load(open(sys.argv[2], encoding="utf-8"))
        deal_hash = deal["deal_hash"].lower()
        if resp.get("deal_hash", "").lower() != deal_hash:
            raise ValueError("response deal_hash does not match deal")
        quote = bytes.fromhex(resp["quote"].lower().removeprefix("0x"))
        rd = report_data_from_quote(quote)
        if rd[:32] != bytes.fromhex(deal_hash):
            raise ValueError("quote report_data does not contain deal_hash")
    except Exception as exc:  # any problem = attestation failed
        print(f"FAILED: {exc}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
