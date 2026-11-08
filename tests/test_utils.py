from django.test import SimpleTestCase

from core.utils import compute_fee, format_ugx, looks_like_academic_dishonesty, normalize_ug_phone, parse_ugx


class MoneyTests(SimpleTestCase):
    def test_format_and_parse(self):
        self.assertEqual(format_ugx(1_250_000), "UGX 1,250,000")
        self.assertEqual(parse_ugx("1,250,000"), 1_250_000)
        self.assertEqual(parse_ugx("UGX 5000"), 5000)
        self.assertIsNone(parse_ugx("12.5"))
        self.assertIsNone(parse_ugx("-3"))

    def test_fee_integer_rounding(self):
        self.assertEqual(compute_fee(100_000, 500), 5_000)
        self.assertEqual(compute_fee(10_001, 1000), 1_000)
        self.assertEqual(compute_fee(15, 1000), 2)  # 1.5 rounds half up
        with self.assertRaises(ValueError):
            compute_fee(-1, 100)
        with self.assertRaises(ValueError):
            compute_fee(100, 20_000)


class PhoneTests(SimpleTestCase):
    def test_ugandan_numbers(self):
        self.assertEqual(normalize_ug_phone("0772 123 456"), "+256772123456")
        self.assertEqual(normalize_ug_phone("+256-772-123-456"), "+256772123456")
        self.assertEqual(normalize_ug_phone("256701234567"), "+256701234567")
        self.assertEqual(normalize_ug_phone("772123456"), "+256772123456")
        self.assertIsNone(normalize_ug_phone("0912345678"))
        self.assertIsNone(normalize_ug_phone("12345"))


class IntegrityTests(SimpleTestCase):
    def test_academic_dishonesty_filter(self):
        self.assertTrue(looks_like_academic_dishonesty("Need someone to write my coursework for Monday"))
        self.assertTrue(looks_like_academic_dishonesty("Exam impersonation needed"))
        self.assertFalse(looks_like_academic_dishonesty("Calculus tutor for 4 sessions"))
