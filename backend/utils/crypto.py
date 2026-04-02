"""
加密解密工具类

使用 AES-256-CBC 加密敏感数据，密钥从 Django SECRET_KEY 派生。
"""

import base64
import hashlib
import os

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


def get_encryption_key() -> bytes:
    """
    从 Django SECRET_KEY 派生 32 字节 AES 密钥。

    使用 SHA-256 哈希确保密钥长度固定为 32 字节（AES-256）。
    """
    from django.conf import settings

    return hashlib.sha256(settings.SECRET_KEY.encode()).digest()[:32]


def encrypt_value(plaintext: str) -> str:
    """
    加密字符串，返回 base64 编码的密文。

    Args:
        plaintext: 要加密的明文字符串

    Returns:
        base64 编码的密文字符串，格式为 IV + Ciphertext

    Example:
        >>> encrypted = encrypt_value("my_password")
        >>> decrypted = decrypt_value(encrypted)
        >>> assert decrypted == "my_password"
    """
    if not plaintext:
        return ""

    key = get_encryption_key()
    iv = os.urandom(16)  # 随机 IV，每次加密结果不同
    cipher = AES.new(key, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(pad(plaintext.encode("utf-8"), 16))

    # 将 IV 和密文拼接后 base64 编码
    return base64.b64encode(iv + ciphertext).decode("ascii")


def decrypt_value(encrypted: str) -> str:
    """
    解密字符串。

    Args:
        encrypted: base64 编码的密文字符串

    Returns:
        解密后的明文字符串

    Raises:
        ValueError: 如果解密失败（密文格式错误或密钥不匹配）
    """
    if not encrypted:
        return ""

    key = get_encryption_key()
    raw = base64.b64decode(encrypted)

    if len(raw) < 32:  # 至少需要 16 字节 IV + 16 字节密文块
        raise ValueError("Invalid encrypted value: too short")

    iv, ciphertext = raw[:16], raw[16:]
    cipher = AES.new(key, AES.MODE_CBC, iv)

    return unpad(cipher.decrypt(ciphertext), 16).decode("utf-8")