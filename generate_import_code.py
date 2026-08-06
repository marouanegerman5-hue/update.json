#!/usr/bin/env python3
"""
generate_import_code.py (نسخة مزينة - تفاعلية)
--------------------------------------------------------------
كي تدوس Run، السكريبت غايسولك واحد واحد على: host, port, user,
password, proxy host, proxy port, payload, use payload — وفالآخر
غايطبع ليك الكود MRVPN://... جاهز، مع واجهة زوينة فالـ Terminal.

المفاتيح (AES + المفتاح الخاص للتوقيع) مكتوبين هنا تحت، بلا حاجة
لأي ملف آخر. ⚠️ الوظيفة (build_import_code, base62, بنية الـblob)
مابدلتش والو — غير الواجهة اللي تزينات.
"""

import base64
import json
import os
import shutil
import struct
import sys
import time

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

# ============================================================
#  الواجهة (ألوان + رسومات) — مايأثرش على المنطق ديال التشفير
# ============================================================
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[92m"
    CYAN = "\033[96m"
    YELLOW = "\033[93m"
    MAGENTA = "\033[95m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    WHITE = "\033[97m"


def term_width(default=64):
    try:
        return max(50, min(shutil.get_terminal_size().columns, 90))
    except Exception:
        return default


def hr(char="─", color=C.DIM):
    print(f"{color}{char * term_width()}{C.RESET}")


def box(title, lines, color=C.CYAN, title_color=C.MAGENTA):
    w = term_width()
    inner = w - 4
    print(f"{color}╭{'─' * (w - 2)}╮{C.RESET}")
    t = f" {title} "
    pad = inner - len(t)
    left = pad // 2
    right = pad - left
    print(f"{color}│{C.RESET} {' ' * left}{title_color}{C.BOLD}{t}{C.RESET}{' ' * right} {color}│{C.RESET}")
    print(f"{color}├{'─' * (w - 2)}┤{C.RESET}")
    for line in lines:
        pad_line = inner - visible_len(line)
        pad_line = max(pad_line, 0)
        print(f"{color}│{C.RESET} {line}{' ' * pad_line} {color}│{C.RESET}")
    print(f"{color}╰{'─' * (w - 2)}╯{C.RESET}")


def visible_len(s):
    # كنحسبو الطول الحقيقي بلا رموز الألوان ANSI باش الصندوق يبقى معدل
    out, i, in_esc = 0, 0, False
    for ch in s:
        if ch == "\x1b":
            in_esc = True
            continue
        if in_esc:
            if ch == "m":
                in_esc = False
            continue
        out += 1
    return out


def spinner(msg, seconds=0.6, color=C.YELLOW):
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    end = time.time() + seconds
    i = 0
    while time.time() < end:
        sys.stdout.write(f"\r{color}{frames[i % len(frames)]} {msg}...{C.RESET}")
        sys.stdout.flush()
        time.sleep(0.05)
        i += 1
    sys.stdout.write(f"\r{C.GREEN}✔ {msg}{' ' * 10}{C.RESET}\n")


def step_header(num, total, label):
    print(f"\n{C.BLUE}{C.BOLD}[{num}/{total}]{C.RESET} {C.WHITE}{label}{C.RESET}")


def banner():
    art = [
        "███╗   ███╗██████╗ ██╗   ██╗██████╗ ███╗   ██╗",
        "████╗ ████║██╔══██╗██║   ██║██╔══██╗████╗  ██║",
        "██╔████╔██║██████╔╝██║   ██║██████╔╝██╔██╗ ██║",
        "██║╚██╔╝██║██╔══██╗╚██╗ ██╔╝██╔═══╝ ██║╚██╗██║",
        "██║ ╚═╝ ██║██║  ██║ ╚████╔╝ ██║     ██║ ╚████║",
        "╚═╝     ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝     ╚═╝  ╚═══╝",
    ]
    print()
    for line in art:
        print(f"{C.CYAN}{C.BOLD}{line}{C.RESET}")
    print(f"{C.MAGENTA}{C.BOLD}          مولّد كود Import (MRVPN://...) {C.RESET}")
    hr("═", C.MAGENTA)


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


def ask(prompt, default=None, secret=False):
    icon = f"{C.YELLOW}➤{C.RESET}"
    shown_default = "•" * min(len(str(default)), 8) if (secret and default) else default
    if default is not None:
        val = _clean(input(f"{icon} {C.CYAN}{prompt}{C.RESET} {C.DIM}[{shown_default}]{C.RESET}: "))
        return val if val else default
    while True:
        val = _clean(input(f"{icon} {C.CYAN}{prompt}{C.RESET}: "))
        if val:
            return val
        print(f"  {C.RED}✘ خاصك تدخل قيمة، ماتخليهاش فارغة.{C.RESET}")


def ask_yes_no(prompt, default=True):
    d = "Y/n" if default else "y/N"
    icon = f"{C.YELLOW}➤{C.RESET}"
    val = _clean(input(f"{icon} {C.CYAN}{prompt}{C.RESET} {C.DIM}({d}){C.RESET}: ")).lower()
    if not val:
        return default
    return val in ("y", "yes", "1", "true")


def mask(s, keep=2):
    if len(s) <= keep:
        return "*" * len(s)
    return s[:keep] + "*" * (len(s) - keep)


def main():
    banner()

    step_header(1, 3, "معطيات السيرفر (SSH)")
    host = ask("SSH Host")
    port = int(ask("SSH Port", "80"))
    user = ask("Username")
    password = ask("Password", secret=True)

    step_header(2, 3, "معطيات الـ Proxy")
    proxy_host = ask("Remote Proxy host", host)
    proxy_port = int(ask("Remote Proxy port", str(port)))

    step_header(3, 3, "الـ Payload")
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

    # ملخص قبل التوليد
    summary_lines = [
        f"{C.WHITE}Host{C.RESET}         : {C.GREEN}{host}:{port}{C.RESET}",
        f"{C.WHITE}User{C.RESET}         : {C.GREEN}{user}{C.RESET}",
        f"{C.WHITE}Password{C.RESET}     : {C.GREEN}{mask(password)}{C.RESET}",
        f"{C.WHITE}Proxy{C.RESET}        : {C.GREEN}{proxy_host}:{proxy_port}{C.RESET}",
        f"{C.WHITE}Use Payload{C.RESET}  : {C.GREEN}{'نعم' if use_payload else 'لا'}{C.RESET}",
    ]
    print()
    box("ملخص المعطيات", summary_lines, color=C.BLUE, title_color=C.CYAN)

    print()
    spinner("كنشفرو ونوقعو الكود", seconds=0.8)

    aes_key = bytes.fromhex(AES_KEY_HEX.strip())
    priv_key = serialization.load_pem_private_key(PRIV_KEY_PEM, password=None)

    code = build_import_code(config, aes_key, priv_key)

    print()
    box("الكود جاهز — انسخو كامل", [f"{C.GREEN}{C.BOLD}{code}{C.RESET}"], color=C.GREEN, title_color=C.GREEN)
    hr("═", C.MAGENTA)
    print(f"{C.DIM}💡 لصق هاد الكود فداخل التطبيق فخانة \"Import\" باش يتقرا القيم أوطوماتيكيا.{C.RESET}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{C.RED}✘ تم الإلغاء.{C.RESET}")
        sys.exit(1)
