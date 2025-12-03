"""
Test script to verify affiliate links are generated correctly with Travelpayouts marker.
Run this to ensure monetization is working before deploying to production.
"""

import sys
sys.path.insert(0, 'bot')

from bot.worker import build_deeplink, build_search_url


def test_links():
    """Test affiliate link generation with different scenarios."""

    marker = "640552"

    print("=" * 70)
    print("TESTING AFFILIATE LINK GENERATION")
    print("=" * 70)
    print()

    # Test 1: Deeplink with marker (Russian)
    print("TEST 1: Deeplink (Russian language)")
    deeplink_path = "/flights/MOW-LED?depart_date=2025-05-12&adults=1"
    result = build_deeplink(deeplink_path, marker=marker, language="ru")
    expected = f"https://aviasales.ru{deeplink_path}&marker={marker}"
    print(f"  Input path: {deeplink_path}")
    print(f"  Expected:   {expected}")
    print(f"  Got:        {result}")
    print(f"  ✓ PASSED" if marker in result and "aviasales.ru" in result else "  ✗ FAILED")
    print()

    # Test 2: Deeplink with marker (English)
    print("TEST 2: Deeplink (English language)")
    result = build_deeplink(deeplink_path, marker=marker, language="en")
    expected = f"https://aviasales.com{deeplink_path}&marker={marker}"
    print(f"  Input path: {deeplink_path}")
    print(f"  Expected:   {expected}")
    print(f"  Got:        {result}")
    print(f"  ✓ PASSED" if marker in result and "aviasales.com" in result else "  ✗ FAILED")
    print()

    # Test 3: Search URL with marker (Russian)
    print("TEST 3: Search URL (Russian language)")
    origin = "MOW"
    destination = "LED"
    departure = "2025-05-12T10:30:00"
    result = build_search_url(origin, destination, departure, marker=marker, language="ru")
    print(f"  Route:    {origin} → {destination}")
    print(f"  Date:     {departure}")
    print(f"  Got:      {result}")
    print(f"  ✓ PASSED" if marker in result and "aviasales.ru" in result else "  ✗ FAILED")
    print()

    # Test 4: Search URL with marker (English)
    print("TEST 4: Search URL (English language)")
    result = build_search_url(origin, destination, departure, marker=marker, language="en")
    print(f"  Route:    {origin} → {destination}")
    print(f"  Date:     {departure}")
    print(f"  Got:      {result}")
    print(f"  ✓ PASSED" if marker in result and "aviasales.com" in result else "  ✗ FAILED")
    print()

    # Test 5: Deeplink without marker (fallback)
    print("TEST 5: Deeplink without marker (should still work)")
    result = build_deeplink(deeplink_path, marker="", language="ru")
    print(f"  Got:      {result}")
    print(f"  ✓ PASSED" if "marker" not in result and "aviasales.ru" in result else "  ✗ FAILED")
    print()

    # Test 6: None path handling
    print("TEST 6: None path handling")
    result = build_deeplink(None, marker=marker, language="ru")
    print(f"  Got:      {result}")
    print(f"  ✓ PASSED" if result is None else "  ✗ FAILED")
    print()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()
    print("✓ All tests completed. Review results above.")
    print()
    print("IMPORTANT:")
    print(f"  - Your marker ID: {marker}")
    print("  - Russian users → aviasales.ru")
    print("  - English users → aviasales.com")
    print("  - All links should contain ?marker=640552 or &marker=640552")
    print()
    print("Next steps:")
    print("  1. Restart the worker: cd bot && python worker.py")
    print("  2. Create a test subscription in your bot")
    print("  3. Wait for a flight notification")
    print("  4. Click the booking link and verify it contains your marker")
    print("  5. Check Travelpayouts dashboard for click statistics")
    print()


if __name__ == "__main__":
    test_links()
