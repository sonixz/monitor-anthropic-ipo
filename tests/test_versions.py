"""Versions: what changed from Amendment No. 2 to Amendment No. 3, each side with its source."""

from __future__ import annotations

from ipo_monitor.facts import Fact, Facts
from ipo_monitor.render import render_page
from ipo_monitor.versions import compare, history_ref, versions


def fact(fact_id: str, value: float | str, as_filed: str = "") -> Fact:
    return Fact(
        id=fact_id,
        title=fact_id,
        label="FILED",
        value=value,
        unit="shares",
        as_filed=as_filed or str(value),
        quote="q",
    )


def test_compare_finds_changed_added_and_removed() -> None:
    older = {f.id: f for f in (fact("a", 1), fact("b", 2), fact("c", 3), fact("doc.x", 1))}
    newer = {f.id: f for f in (fact("a", 1), fact("b", 5), fact("d", 4), fact("doc.x", 2))}
    assert compare(older, newer) == [("b", "changed"), ("d", "added"), ("c", "removed")]
    # Same value, other words (Class A only, then Class A and Class N): listed too.
    reworded = {"a": fact("a", 1, "up to 1 of Class A and Class N")}
    assert compare({"a": fact("a", 1)}, reworded) == [("a", "changed")]


def test_amendment_2_to_3(facts: Facts) -> None:
    shown, steps = versions(facts)
    (step,) = steps
    assert (step.older.title, step.newer.title) == (
        "Form S-1/A, Amendment No. 2",
        "Form S-1/A, Amendment No. 3",
    )
    ids = [c.id for c in step.changes]
    # By hand from the two filings: Nasdaq approved the listing, and 20 of the 23 lock-up steps
    # moved when the table split Class A and Class N (steps 6, 12 and 23 kept their totals).
    assert ids[0] == "offering.listing"
    unlocks = [i for i in ids if i.startswith("unlock.")]
    assert len(unlocks) == 20
    assert {"unlock.06", "unlock.12", "unlock.23"}.isdisjoint(unlocks)
    assert len(ids) == 21
    assert not any(i.startswith("doc.") for i in ids)  # the filing's date is on the top line

    listing = step.changes[0]
    assert shown.text(listing.before or "") == "applied for"
    assert shown.text(listing.after or "") == "approved"
    # The earlier value opens Amendment No. 2, the later one Amendment No. 3.
    before = shown.document_of(history_ref("s1a2", "unlock.02"))
    after = shown.document_of("unlock.02")
    assert before is not None
    assert before.filed == "2026-11-10"
    assert after is not None
    assert after.filed == "2026-11-17"
    assert shown.num(history_ref("s1a2", "unlock.02")) == 299_000_000
    assert shown.num("unlock.02") == 303_000_000
    step_2 = next(c for c in step.changes if c.id == "unlock.02")
    assert (step_2.when, step_2.style) == ("unlock.02.when", "m")
    # The page's own facts are untouched.
    assert len(shown) == len(facts) + 21


def test_the_page_says_which_filing_and_what_changed(facts: Facts) -> None:
    html = render_page(facts, release="test").html
    start = html.index('<section class="status overview"')
    overview = html[start : html.index("</dl>", start)]
    assert "Form S-1/A, Amendment No. 3" in overview
    assert 'href="#history">what changed</a>' in overview
    assert 'href="#history"><kbd aria-hidden="true">h</kbd>history</a>' in html
    panel = html[html.index('id="history"') : html.index("</section>", html.index('id="history"'))]
    assert panel.count("<tr>") == 22  # a header row and 21 changes
    # The listing shows at once; the 20 lock-up steps are folded until asked for (owner).
    main, folded = panel.split('<details class="fold changes-more">')
    assert "Listing on the exchange" in main
    assert "unlock" not in main
    assert folded.count("<tr>") == 20
    assert 'popovertarget="src-s1a2-unlock-02"' in panel
    assert 'popovertarget="src-unlock-02"' in panel
    card = html[html.index('<div popover id="src-s1a2-unlock-02"') :][:3000]
    assert "Amendment No. 2" in card
    assert "Up to 299 million shares of Class A common stock" in card


def test_without_history_there_is_no_panel(facts: Facts) -> None:
    alone = Facts([], ())
    alone._by_id = {i: facts.get(i) for i in facts.ids()}
    alone._doc_of = {i: facts.filing.id for i in facts.ids() if facts.document_of(i)}
    alone.documents = {facts.filing.id: facts.filing}
    alone._filing = facts.filing.id
    html = render_page(alone, release="test").html
    assert 'id="history"' not in html
    assert "what changed" not in html
