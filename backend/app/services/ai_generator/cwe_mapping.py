"""
CWE-to-task-type relevance mapping for CTF challenge generation.

Used to:
1. Filter kb_entries by CWE relevance during RAG retrieval
2. Infer the best task type for a given CVE (CVE-first generation)
"""
from __future__ import annotations

from typing import Optional

# Maps CWE IDs to the task types they are most relevant for.
# A CWE can map to multiple task types.
CWE_TO_TASK_TYPES: dict[str, list[str]] = {
    # ── Cryptography ────────────────────────────────────────────────────────
    "CWE-327": ["crypto_text_web"],       # Use of a broken or risky cryptographic algorithm
    "CWE-328": ["crypto_text_web"],       # Use of weak hash
    "CWE-326": ["crypto_text_web"],       # Inadequate encryption strength
    "CWE-325": ["crypto_text_web"],       # Missing required cryptographic step
    "CWE-330": ["crypto_text_web"],       # Use of insufficiently random values
    "CWE-331": ["crypto_text_web"],       # Insufficient entropy
    "CWE-338": ["crypto_text_web"],       # Use of cryptographically weak PRNG
    "CWE-347": ["crypto_text_web"],       # Improper verification of cryptographic signature
    "CWE-757": ["crypto_text_web"],       # Selection of less-secure algorithm during negotiation
    "CWE-916": ["crypto_text_web"],       # Use of password hash with insufficient computational effort
    "CWE-311": ["crypto_text_web"],       # Missing encryption of sensitive data
    "CWE-319": ["crypto_text_web"],       # Cleartext transmission of sensitive information
    "CWE-522": ["crypto_text_web"],       # Insufficiently protected credentials
    "CWE-256": ["crypto_text_web"],       # Plaintext storage of password
    "CWE-321": ["crypto_text_web"],       # Use of hard-coded cryptographic key
    "CWE-334": ["crypto_text_web"],       # Small space of random values
    "CWE-760": ["crypto_text_web"],       # Use of a one-way hash with a predictable salt

    # ── Forensics / Information Disclosure ──────────────────────────────────
    "CWE-200": ["forensics_image_metadata"],  # Exposure of sensitive information to unauthorized actor
    "CWE-201": ["forensics_image_metadata"],  # Insertion of sensitive information into sent data
    "CWE-203": ["forensics_image_metadata"],  # Observable discrepancy
    "CWE-209": ["forensics_image_metadata"],  # Generation of error message containing sensitive info
    "CWE-212": ["forensics_image_metadata"],  # Improper removal of sensitive information before storage
    "CWE-359": ["forensics_image_metadata"],  # Exposure of private personal information
    "CWE-497": ["forensics_image_metadata"],  # Exposure of sensitive system information
    "CWE-532": ["forensics_image_metadata"],  # Insertion of sensitive information into log file
    "CWE-538": ["forensics_image_metadata"],  # Insertion of sensitive information into externally-accessible file
    "CWE-540": ["forensics_image_metadata"],  # Inclusion of sensitive information in source code
    "CWE-615": ["forensics_image_metadata"],  # Inclusion of sensitive information in source code comments

    # Dual: forensics + crypto
    "CWE-312": ["crypto_text_web", "forensics_image_metadata"],  # Cleartext storage of sensitive information
    "CWE-798": ["crypto_text_web", "forensics_image_metadata"],  # Use of hard-coded credentials

    # ── Web / XSS ───────────────────────────────────────────────────────────
    "CWE-79":  ["web_static_xss"],        # Improper neutralization of input during web page generation (XSS)
    "CWE-80":  ["web_static_xss"],        # Improper neutralization of script-related HTML tags
    "CWE-81":  ["web_static_xss"],        # Improper neutralization of script error message contents
    "CWE-83":  ["web_static_xss"],        # Improper neutralization of script in attributes
    "CWE-84":  ["web_static_xss"],        # Improper neutralization of encoded URI schemes in a web page
    "CWE-86":  ["web_static_xss"],        # Improper neutralization of invalid characters in identifiers
    "CWE-87":  ["web_static_xss"],        # Improper neutralization of alternate XSS syntax
    "CWE-116": ["web_static_xss"],        # Improper encoding or escaping of output
    "CWE-184": ["web_static_xss"],        # Incomplete list of disallowed inputs
    "CWE-20":  ["web_static_xss"],        # Improper input validation (broad, but often web)
    "CWE-352": ["web_static_xss"],        # Cross-site request forgery
    "CWE-601": ["web_static_xss"],        # URL redirection to untrusted site (open redirect)

    # ── Chat / LLM / Injection ──────────────────────────────────────────────
    "CWE-74":  ["chat_llm"],              # Improper neutralization of special elements (injection)
    "CWE-77":  ["chat_llm"],              # Improper neutralization of special elements in command
    "CWE-94":  ["chat_llm"],              # Improper control of generation of code (code injection)
    "CWE-1336": ["chat_llm"],             # Improper neutralization of special elements (template injection)
    "CWE-706": ["chat_llm"],              # Use of incorrectly-resolved name or reference
    "CWE-114": ["chat_llm"],              # Process control
}

# Reverse mapping: task_type -> set of relevant CWE IDs
TASK_TYPE_TO_CWES: dict[str, set[str]] = {}
for _cwe, _task_types in CWE_TO_TASK_TYPES.items():
    for _tt in _task_types:
        TASK_TYPE_TO_CWES.setdefault(_tt, set()).add(_cwe)

# Human-readable CWE descriptions for prompt context
CWE_DESCRIPTIONS: dict[str, str] = {
    "CWE-327": "использование устаревшего или небезопасного криптографического алгоритма",
    "CWE-328": "использование слабой хеш-функции",
    "CWE-326": "недостаточная длина или сложность ключа шифрования",
    "CWE-330": "использование недостаточно случайных значений",
    "CWE-331": "недостаточная энтропия при генерации ключей",
    "CWE-338": "использование криптографически слабого генератора псевдослучайных чисел",
    "CWE-311": "отсутствие шифрования конфиденциальных данных",
    "CWE-312": "хранение конфиденциальной информации в открытом виде",
    "CWE-319": "передача конфиденциальных данных по незащищённому каналу",
    "CWE-798": "использование жёстко закодированных учётных данных (hard-coded credentials)",
    "CWE-321": "использование жёстко закодированного криптографического ключа",
    "CWE-200": "раскрытие конфиденциальной информации неавторизованному пользователю",
    "CWE-212": "неполное удаление конфиденциальных данных перед хранением или передачей",
    "CWE-532": "запись конфиденциальной информации в лог-файлы",
    "CWE-538": "включение конфиденциальных данных в файлы, доступные извне",
    "CWE-79": "межсайтовый скриптинг (XSS) — выполнение произвольного кода в браузере жертвы",
    "CWE-80": "внедрение script-тегов через пользовательский ввод",
    "CWE-87": "обход XSS-фильтров с использованием альтернативного синтаксиса",
    "CWE-116": "некорректное экранирование или кодирование вывода",
    "CWE-74": "внедрение специальных элементов во входные данные (инъекция)",
    "CWE-94": "инъекция кода через управление генерацией программного кода",
    "CWE-1336": "инъекция через шаблоны или управление потоком данных (prompt injection)",
}

# Per-task-type guidance for how to use a CWE in task mechanics
CWE_TASK_RELEVANCE_HINTS: dict[str, dict[str, str]] = {
    "crypto_text_web": {
        "CWE-327": "слабого алгоритма шифрования — используй устаревший шифр (caesar, rot13, substitution) как отражение уязвимости",
        "CWE-326": "короткого ключа шифрования — используй xor с 1-2 символьным ключом или малый сдвиг caesar",
        "CWE-311": "отсутствия шифрования — данные закодированы, но не зашифрованы (base64, hex)",
        "CWE-312": "хранения данных в открытом виде — сценарий про обнаружение незашифрованного секрета",
        "CWE-330": "слабого генератора случайных чисел — предсказуемый ключ vigenere или повторяющийся xor",
        "CWE-798": "жёстко закодированного ключа — используй aes_ecb с очевидным ключом типа 'password' или 'admin'",
        "CWE-321": "жёстко закодированного криптоключа — ключ можно найти в открытых данных",
        "CWE-319": "передачи данных в открытом виде — перехваченное сообщение нужно декодировать",
    },
    "forensics_image_metadata": {
        "CWE-200": "раскрытия конфиденциальных данных — флаг скрыт в метаданных как 'утёкшая' информация",
        "CWE-212": "неполного удаления данных — флаг остался в EXIF после попытки очистки",
        "CWE-532": "данных в логах — сценарий про обнаружение следов в файловых метаданных",
        "CWE-538": "конфиденциальных данных в файле — флаг внедрён в поле метаданных изображения",
        "CWE-312": "хранения в открытом виде — флаг хранится незашифрованным в метаданных",
        "CWE-798": "жёстко закодированных данных — флаг-пароль обнаружен в поле Author или Copyright",
    },
    "web_static_xss": {
        "CWE-79": "классического XSS — внедрение <script> через уязвимое поле формы",
        "CWE-80": "XSS через script-теги — поле ввода отражается без санитизации",
        "CWE-87": "обхода XSS-фильтра — используй альтернативный синтаксис (onerror, SVG, javascript:)",
        "CWE-116": "некорректного экранирования — payload обходит неполную санитизацию",
        "CWE-20": "некорректной валидации ввода — поле отражает произвольный HTML/JS",
    },
    "chat_llm": {
        "CWE-74": "инъекции команд — пользователь может переопределить инструкции системного промпта",
        "CWE-94": "инъекции кода — модель выполняет инструкции через псевдокод или шаблоны",
        "CWE-1336": "prompt injection — специально сформированный запрос меняет поведение LLM",
    },
}

# Fallback: attack_vector to likely task types for CVEs without CWE data
ATTACK_VECTOR_TO_TASK_TYPES: dict[str, list[str]] = {
    "NETWORK": ["web_static_xss", "crypto_text_web", "chat_llm"],
    "ADJACENT_NETWORK": ["crypto_text_web"],
    "LOCAL": ["forensics_image_metadata"],
    "PHYSICAL": ["forensics_image_metadata"],
}

# All implemented task types (used for infer_task_type fallback)
IMPLEMENTED_TASK_TYPES = {"crypto_text_web", "forensics_image_metadata", "web_static_xss", "chat_llm"}


def get_relevant_cwes_for_task_type(task_type: str) -> list[str]:
    """Return list of CWE IDs relevant to the given task type."""
    return sorted(TASK_TYPE_TO_CWES.get(task_type, set()))


def infer_task_type(
    cwe_ids: list[str],
    attack_vector: Optional[str] = None,
    implemented_only: bool = True,
) -> str:
    """Infer the best task type for a CVE based on its CWE IDs and attack vector.

    Returns the task type with the highest relevance score.
    Falls back to 'crypto_text_web' when no match is found.
    """
    scores: dict[str, float] = {tt: 0.0 for tt in IMPLEMENTED_TASK_TYPES}

    for cwe in cwe_ids:
        for task_type in CWE_TO_TASK_TYPES.get(cwe, []):
            if task_type in scores:
                scores[task_type] += 1.0

    # Bonus for attack vector match
    if attack_vector:
        for task_type in ATTACK_VECTOR_TO_TASK_TYPES.get(attack_vector, []):
            if task_type in scores:
                scores[task_type] += 0.5

    best = max(scores, key=lambda tt: scores[tt])
    if scores[best] == 0.0:
        return "crypto_text_web"  # universal fallback
    return best


def get_cwe_hint_for_task(task_type: str, cwe_ids: list[str]) -> Optional[str]:
    """Return the best CWE-to-mechanics hint for the task type, given a list of CVE CWEs."""
    hints = CWE_TASK_RELEVANCE_HINTS.get(task_type, {})
    for cwe in cwe_ids:
        if cwe in hints:
            desc = CWE_DESCRIPTIONS.get(cwe, cwe)
            return f"Уязвимость связана с {hints[cwe]} ({cwe}: {desc})"
    return None
