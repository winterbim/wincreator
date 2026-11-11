# Rates service v2 (documentation last reviewed 2024-01)

`GET https://rates.internal.example/v2/rates/<CURRENCY>`

- `200` with JSON body `{"currency": "USD", "rate": "1.0842"}` — `rate` is a
  decimal string.
- `404` when the currency is unknown.
- Any other status, invalid JSON, a missing `rate`, or a `rate` that is not a
  decimal string is a malformed response.

Currency codes are three ASCII letters and are sent upper-case.
