# ANALYSIS · monitor-anthropic-ipo

> The method behind the page, in plain language. Version 0.1, 2026-11-15. It is the agent's proposal, to be refined with the owner; from Loop 002 it is also what the AI will follow.

This is not investment advice. It is a way of reading an IPO filing so that a reader knows what they are buying.

## The questions an analyst asks

| # | Question | Where the page answers it | Status |
| --- | --- | --- | --- |
| 1 | How much does it sell, and how fast is that growing? | GROWTH | Loop 001 |
| 2 | What does it cost to produce? | GROWTH (compute cost, revenue per compute dollar, operating result) | Loop 001 |
| 3 | Does it have enough money, against what it has promised to pay? | CONTRACTS, EV BRIDGE | Loop 001 |
| 4 | Who controls it? | Not yet | Later |
| 5 | What can go wrong? | Not yet | Later |
| 6 | What is it worth, and what must be true for the price to make sense? | VALUE, EV BRIDGE | Loop 001 (first half) |
| 7 | What changed since last time? | Not yet | Loop 002 |

## Four kinds of statement

| Label | Meaning | How to check it |
| --- | --- | --- |
| FILED | Copied from an SEC filing, by code | The source card quotes the passage and gives the page |
| CALC | Our arithmetic on other numbers | The source card shows the formula and every input |
| PRESS | Reported by a news outlet | The source card quotes the article and links to it |
| AI | An explanation written by a model | Not used yet. It will cite the numbers it relies on |

A number never changes label. A CALC built on FILED inputs is still CALC: the choice of what to add is ours.

## How we read value

**The value of a company is its share count times the share price.** The price range is filed ($70 to $78). The difficulty is the share count: the filing gives several, and they differ by billions.

1. **Shares outstanding after the IPO.** What exists the day after: the filing's own total. This is the smallest honest count.
2. **Diluted.** Plus every share someone already has a right to: the notes Amazon still holds and will convert, employee stock options, employee RSUs, and the few shares issued since the last balance sheet. We count options and RSUs in full, vested or not.
3. **Reserved shares are not counted.** The filing reserves about 2 billion shares for future employee grants. Nobody holds them. The widely quoted "fully diluted" figures include them; we show that count separately and say what it adds and what it leaves out.

When two sources disagree on the value, the first thing to compare is their share count.

## How we read what the price buys

**Enterprise value** is the price of the business itself. Start from the diluted value; take away the cash the company will hold after the offering, because a buyer gets that cash; take away what option holders would pay to exercise; add borrowings (there are none drawn).

We then set that price against revenue, three ways, because a fast-growing company has three very different "revenues": the last twelve months, the latest quarter times four, and the company's own Run-Rate Revenue (its most recent weeks, annualized). The multiple falls as the measure gets more recent. Which one to trust depends on whether the growth lasts, and the page does not answer that for the reader.

## How we read contracts

Two numbers, side by side: what customers have signed to pay the company, and what the company has signed to pay its suppliers. For Anthropic the second is about 65 times the first, almost all of it for compute and infrastructure. That gap is not a verdict. It says that revenue is mostly billed on usage, without long commitments, while costs are committed years ahead. We show when the spending falls due, what it is made of, how much can still be cancelled, and how the cash on hand compares with the next twelve months.

## How we read losses

A net loss can come from running the business or from accounting. In the first nine months of 2026, about nine tenths of the net loss is the change in fair value of convertible notes and derivatives, which the filing ties to the rise in the company's own valuation. We separate it from the operating loss, and we say which is which. We do not call the accounting part "fake": it is a real entry in the accounts, but it is not money spent on operations.

## Rules for every figure

1. If it is not in a source, it is not on the page.
2. Extracted by code, never retyped.
3. Checked against another place where the source states the same thing: quarters against the year, a sentence against a table, parts against their total.
4. Shown with the precision of the source. "Approximately" stays approximate.
5. An assumption is a visible input, never a hidden constant.

## What we refuse to conclude

- Whether the stock is cheap or expensive. We show what the price implies.
- Any forecast. The filing gives no guidance and says growth will slow.
- Anything about the first day of trading before it happens.

## For the AI, from Loop 002

When a model writes on this page, it will be given this file, the facts and the calculations, and nothing else. It may explain and compare; it may not introduce a number. Every sentence it writes about a figure must point to that figure's id. If the data does not answer the question, it says so.
