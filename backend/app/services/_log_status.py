import logging

_GREEN  = "\033[92m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_BOLD   = "\033[1m"
_RESET  = "\033[0m"

_STAGE_EMOJI = {
    "INIT":        "▶",
    "FETCHING":    "▶",
    "TRANSLATING": "▶",
    "EMBEDDING":   "▶",
    "SUCCESS":     "🟢",
    "ERROR":       "🔴",
}


def db_emoji(stage: str) -> str:
    return _STAGE_EMOJI.get(stage, "▶")


def status_ok(log: logging.Logger, msg: str) -> None:
    log.info("%s%s🟢 OK%s %s", _GREEN, _BOLD, _RESET, msg)


def status_fail(log: logging.Logger, msg: str) -> None:
    log.error("%s%s🔴 FAIL%s %s", _RED, _BOLD, _RESET, msg)


def status_warn(log: logging.Logger, msg: str) -> None:
    log.warning("%s⚠  WARN%s %s", _YELLOW, _RESET, msg)


def status_stage(log: logging.Logger, stage: str, msg: str) -> None:
    log.info("%s▶ %s%s %s", _BOLD, stage, _RESET, msg)


def status_banner_ok(log: logging.Logger, title: str, details: str) -> None:
    log.info("%s%s══ ✅ %s ══%s\n    %s", _GREEN, _BOLD, title, _RESET, details)


def status_banner_fail(log: logging.Logger, title: str, details: str) -> None:
    log.error("%s%s══ ❌ %s ══%s\n    %s", _RED, _BOLD, title, _RESET, details)


def status_banner_warn(log: logging.Logger, title: str, details: str) -> None:
    log.warning("%s%s══ ⚠  %s ══%s\n    %s", _YELLOW, _BOLD, title, _RESET, details)
