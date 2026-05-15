---
id: SPEC-001
title: Apply discount at checkout
status: in-progress
labels: [checkout, billing, discounts]
priority: P1
---

# Apply discount at checkout

## Context
Customers receive promo codes via email campaigns. They expect to apply the code at checkout and see the discount reflected immediately in the subtotal.

## Acceptance criteria

1. **Valid promo code** — A logged-in user with items in their cart enters a valid, non-expired promo code. The discount is applied to the subtotal and the new total is displayed.
2. **Invalid promo code** — User enters a code that does not exist. An inline error appears: "Promo code not recognized." Subtotal is unchanged.
3. **Expired promo code** — User enters a known code whose expiration is in the past. An inline error appears: "This code has expired." Subtotal is unchanged.
4. **Empty cart** — User enters any code with an empty cart. An inline error appears: "Add items to your cart first." No promo lookup happens server-side.

## Out of scope
- Promo code creation / admin flow
- Stacking multiple codes (one code per order in v1)
- Currency conversion for international codes

## Notes for QA
- Promo codes are case-insensitive
- The discount API endpoint is `POST /api/discounts/apply`
- Test users: `qa+promo@example.com` (active codes), `qa+expired@example.com` (expired codes)
