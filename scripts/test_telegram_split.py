
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path("/Users/liusong/Downloads/nanobot").resolve()))

from nanobot.channels.telegram import _split_message

def test_split():
    # Test 1: Short message
    print("Running Test 1...")
    text1 = "Short message"
    res1 = _split_message(text1, limit=20)
    print(f"Result: {res1}")
    assert res1 == ["Short message"]

    # Test 2: Split at double newline
    print("\nRunning Test 2...")
    text2 = "Paragraph 1\n\nParagraph 2\n\nParagraph 3"
    # limit 25. "Paragraph 1\n\n" is 13 chars. "Paragraph 2" is 11 chars.
    # Total "Paragraph 1\n\nParagraph 2" is 24 chars.
    # But \n\n starts at 24, needing index 25 for completion.
    chunks2 = _split_message(text2, limit=25)
    print(f"Chunks: {chunks2}")
    # Based on rfind logic, it should find index 11
    assert chunks2 == ["Paragraph 1", "Paragraph 2\n\nParagraph 3"]

    # Test 3: Split at single newline
    print("\nRunning Test 3...")
    text3 = "Line 1\nLine 2\nLine 3"
    chunks3 = _split_message(text3, limit=10)
    print(f"Chunks: {chunks3}")
    assert chunks3 == ["Line 1", "Line 2", "Line 3"]

    # Test 4: Hard split
    print("\nRunning Test 4...")
    text4 = "abcdefghij"
    chunks4 = _split_message(text4, limit=5)
    print(f"Chunks: {chunks4}")
    assert chunks4 == ["abcde", "fghij"]

    # Test 5: Real-world-ish long message
    text5 = "A" * 5000
    chunks5 = _split_message(text5, limit=3500)
    assert len(chunks5) == 2
    assert len(chunks5[0]) == 3500
    assert len(chunks5[1]) == 1500
    print("Test 5 passed")

if __name__ == "__main__":
    try:
        test_split()
        print("\nAll internal split tests passed!")
    except AssertionError as e:
        print(f"\nTest failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        sys.exit(1)
