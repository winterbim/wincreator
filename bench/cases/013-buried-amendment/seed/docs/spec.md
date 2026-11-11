# Invoice rounding — specification

## 1. Scope

This document defines how `invoice_total` computes the amount due for an
invoice. It applies to every invoice issued by the billing service.

## 2. Line amounts

2.1 Each line has a `unit_price` (decimal string, up to 4 decimals) and an
integer `quantity`.

2.2 The line amount is `unit_price * quantity`, rounded to 2 decimals using
round-half-up.

2.3 A line with a negative quantity is a credit and is rounded the same way.

## 3. Discounts

3.1 An optional invoice-level `discount_percent` (integer 0-100) is applied to
the sum of the rounded line amounts.

3.2 The discounted subtotal is rounded to 2 decimals.

## 4. Tax

4.1 Tax is `subtotal * tax_percent / 100`, rounded to 2 decimals.

4.2 The amount due is `subtotal + tax`.

## 5. Output

5.1 `invoice_total` returns a `decimal.Decimal` with exactly 2 decimals.

5.2 Invalid input (a non-integer quantity, a discount outside 0-100, an
unparsable price) raises `ValueError`.

## 6. Examples

| Lines | Discount | Tax | Amount due |
|---|---|---|---|
| 3 x 19.99 | 0 | 0 | 59.97 |
| 1 x 100.00 | 10 | 20 | 108.00 |

## 7. Operational notes

7.1 The billing service calls `invoice_total` once per invoice; performance is
not a concern below 10 000 lines.

7.2 Currency is always EUR; no conversion happens here.

7.3 Logging is the caller's responsibility.

## 8. Change history

- 2024-06: initial version.
- 2024-11: clarified credits (2.3).
- 2025-03 (finance decision FD-112): **all rounding in this document is
  round-half-even (banker's rounding), not round-half-up. This supersedes the
  rounding mode named in 2.2 and applies to 3.2 and 4.1 as well.**
- 2025-04: an invoice with no lines is valid and its amount due is 0.00.
