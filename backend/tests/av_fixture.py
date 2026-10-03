"""TEST-ONLY antivirus double (Phase 12B D17: "TEST: EICAR + test double"). Registered by the test suite only; it is marked
`is_test_double`, so `get_scanner()` refuses it in production. It reports CLEAN only because the TEST environment defines it to; it is
never available to the running application."""
from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from app.core.config import get_settings
from app.integrations import malware
from app.integrations.malware import EICAR, ScannerUnavailable, ScanResult

NAME = "test-double"


@dataclass
class TestDoubleScanner:
    __test__ = False                   # not a pytest test class
    mode: str = "clean"                # clean | unavailable | infect-all
    name: str = NAME
    is_test_double: bool = True
    calls: int = 0

    def scan(self, data: bytes, filename: str | None = None) -> ScanResult:
        self.calls += 1
        if self.mode == "unavailable":
            raise ScannerUnavailable("test double: engine unreachable")
        if EICAR in data or self.mode == "infect-all":
            return ScanResult("INFECTED", self.name, "test-double-1", "EICAR-Test-File", "test double detection")
        return ScanResult("CLEAN", self.name, "test-double-1", None, None)

    def health(self) -> list[str]:
        return ["test double: engine unreachable"] if self.mode == "unavailable" else []


@pytest.fixture()
def av(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestDoubleScanner]:
    scanner = TestDoubleScanner()
    monkeypatch.setitem(malware._REGISTRY, NAME, lambda _s: scanner)
    monkeypatch.setattr(get_settings(), "MALWARE_SCANNER", NAME)
    malware.get_scanner.cache_clear()
    yield scanner
    malware.get_scanner.cache_clear()
