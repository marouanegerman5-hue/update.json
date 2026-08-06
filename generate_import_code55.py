#!/usr/bin/env python3
"""
generate_import_code.py (نسخة تفاعلية - كتسولك على كل قيمة)
--------------------------------------------------------------
كي تدوس Run، السكريبت غايسولك واحد واحد على: host, port, user,
password, proxy host, proxy port, payload, use payload — وفالآخر
غايطبع ليك الكود MRVPN://... جاهز.

المفاتيح (AES + المفتاح الخاص للتوقيع) مكتوبين هنا تحت، بلا حاجة
لأي ملف آخر.
"""

import base64
import json
import os
import struct

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ============================================================
#  المفاتيح — ماتبدلش هادو (نفسهم اللي فـ tools_bundle الأصلي)
# ============================================================
AES_KEY_HEX = "00ef62ad38bd67e8942d83ba32c0d9bd8f4945442b11f02cc118eea31c60f071"

PRIV_KEY_PEM = b"""-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgCxX96JhNeeXun1Av
sPjmDB+mA54NGXSREoOdNJeb7W6hRANCAARDjlVJ4kX0wHWgMp3QkbUGKUlOhOXT
u4kpj8tb2G5Q6QOk3RGRHbuR7qBJQPjYl3qPKY4WRMfT8Oet8YTmCNlS
-----END PRIVATE KEY-----
"""

VERSION = 0x01
PREFIX = "MRVPN://"
ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

# --- ألوان (ANSI) باش الواجهة تبان زوينة فـ Terminal/Console ---
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    CYAN = "\033[96m"
    YELLOW = "\033[93m"
    MAGENTA = "\033[95m"
    RED = "\033[91m"


# قيم افتراضية (كتظهر بين قوسين)، دوس Enter بلا كتابة باش تخدم بيهم،
# أو اكتب payload ديالك بحال ما بغيتي هنا مباشرة — بلا ما تحتاج تعدل
# شي حاجة فالسكريبت نفسو.
DEFAULT_PAYLOAD = (
    "GET /cdn-cgi HTTP/1.1[lf]Host: guest.pscp.tv[lf][lf]"
    "ACL / HTTP/1.1[lf]Host: [host][crlf]Connection: [lf]Upgrade: Websocket[lf][lf]"
)


def base62_encode(data: bytes) -> str:
    if not data:
        return ""
    num = int.from_bytes(data, "big")
    digits = []
    while num > 0:
        num, rem = divmod(num, 62)
        digits.append(ALPHABET[rem])
    leading_zeros = 0
    for b in data:
        if b == 0:
            leading_zeros += 1
        else:
            break
    return (ALPHABET[0] * leading_zeros) + "".join(reversed(digits))


def build_import_code(config: dict, aes_key: bytes, priv_key) -> str:
    plaintext = json.dumps(config, separators=(",", ":")).encode("utf-8")

    iv = os.urandom(12)
    aesgcm = AESGCM(aes_key)
    ciphertext = aesgcm.encrypt(iv, plaintext, None)

    signed_part = bytes([VERSION]) + struct.pack(">H", len(ciphertext)) + iv + ciphertext
    signature = priv_key.sign(signed_part, ec.ECDSA(hashes.SHA256()))

    blob = signed_part + struct.pack(">H", len(signature)) + signature
    return PREFIX + base62_encode(blob)


def _clean(s: str) -> str:
    # كنحيدو حروف التحكم الخفية (بحال NUL/^@) اللي ممكن تتزاد ملي
    # تلصق من شريط اقتراحات الكيبورد بدل Paste العادي — هاد الحروف
    # مايبانوش بالعين بصح كيبدلو القيمة فعليا (host مختلف كليا).
    return "".join(ch for ch in s if ch.isprintable() or ch in "\t").strip()


def ask(prompt, default=None):
    if default is not None:
        val = _clean(input(f"{C.CYAN}{prompt}{C.RESET} {C.YELLOW}[{default}]{C.RESET}: "))
        return val if val else default
    while True:
        val = _clean(input(f"{C.CYAN}{prompt}{C.RESET}: "))
        if val:
            return val
        print(f"{C.RED}  -> خاصك تدخل قيمة، ماتخليهاش فارغة.{C.RESET}")


def ask_yes_no(prompt, default=True):
    d = "Y/n" if default else "y/N"
    val = _clean(input(f"{C.CYAN}{prompt}{C.RESET} {C.YELLOW}({d}){C.RESET}: ")).lower()
    if not val:
        return default
    return val in ("y", "yes", "1", "true")


def main():
    print(f"\n{C.MAGENTA}{C.BOLD}=== توليد كود Import (MRVPN://...) ==={C.RESET}\n")

    host = ask("SSH Host")
    port = int(ask("SSH Port", "80"))
    user = ask("Username")
    password = ask("Password")
    proxy_host = ask("Remote Proxy host", host)
    proxy_port = int(ask("Remote Proxy port", str(port)))
    use_payload = ask_yes_no("Use Payload?", True)
    payload = ask("Payload", DEFAULT_PAYLOAD) if use_payload else ""

    config = {
        "h": host,
        "p": port,
        "u": user,
        "w": password,
        "ph": proxy_host,
        "pp": proxy_port,
        "pl": payload,
        "up": use_payload,
    }

    aes_key = bytes.fromhex(AES_KEY_HEX.strip())
    priv_key = serialization.load_pem_private_key(PRIV_KEY_PEM, password=None)

    code = build_import_code(config, aes_key, priv_key)
    print(f"\n{C.GREEN}{C.BOLD}=== الكود جاهز، انسخو كامل: ==={C.RESET}")
    print(f"{C.GREEN}{code}{C.RESET}\n")


if __name__ == "__main__":
    main()
