# Unit Tests
import pytest

from api.codes import ALPHABET, generate_code


@pytest.mark.parametrize("length", [1, 7, 12])
def test_generate_code_has_requested_length(length):
    assert len(generate_code(length)) == length


def test_generate_code_uses_only_base62_characters():
    code = generate_code(50)
    assert all(ch in ALPHABET for ch in code)


def test_generate_code_is_random():
    codes = {generate_code() for _ in range(1000)}
    assert len(codes) == 1000
