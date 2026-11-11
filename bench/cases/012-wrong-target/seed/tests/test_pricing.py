import unittest

from shop.pricing import line_total


class LineTotalTest(unittest.TestCase):
    def test_small_order_full_price(self):
        self.assertEqual(line_total(1000, 9), 9000)

    def test_bulk_order_gets_ten_percent_off(self):
        self.assertEqual(line_total(1000, 10), 9000)


if __name__ == "__main__":
    unittest.main()
