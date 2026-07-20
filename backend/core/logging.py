import logging
import sys


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def configure_logging(level: int = logging.INFO) -> None:
    """애플리케이션 로거를 콘솔에 연결한다.

    지금까지 설정이 없어 root의 lastResort(WARNING)만 동작했고, 그래서
    코드 곳곳이 print에 의존했다. 콘솔이 cp949여도 죽지 않도록 인코딩
    오류는 대체 문자로 흘려보낸다(print는 여기서 예외를 던진다).
    """

    root = logging.getLogger()
    if any(getattr(handler, "_seoulmate", False) for handler in root.handlers):
        return
    stream = sys.stderr
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(errors="backslashreplace")
        except (ValueError, OSError):
            pass
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter(
        "%(levelname)s %(name)s: %(message)s"
    ))
    handler._seoulmate = True
    root.addHandler(handler)
    root.setLevel(level)


__all__ = ["configure_logging", "get_logger"]

