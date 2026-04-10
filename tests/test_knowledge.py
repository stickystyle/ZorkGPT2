"""Tests for knowledge base guardrails."""

from zorkburr.actions.knowledge import _dedup_items_found, _parse_sections


class TestDedupItemsFound:
    """Tests for _dedup_items_found() structural guardrail."""

    def test_duplicate_items_collapsed_to_one(self):
        """Multiple entries for the same item should keep only the first."""
        kb = (
            "**Items Found:**\n"
            "- Platinum bar — Loud Room (R58) (taken, scores +10)\n"
            "- Platinum bar — Loud Room (R58) (taken; deposited in trophy case R1)\n"
            "- Platinum bar — Loud Room (R58) (taken; dropped in Studio R52)\n"
        )
        result = _dedup_items_found(kb)
        sections = _parse_sections(result)
        assert len(sections["Items Found"]) == 1
        assert "Platinum bar" in sections["Items Found"][0]

    def test_drop_annotations_stripped(self):
        """Transient drop/deposit/left annotations should be stripped."""
        kb = (
            "**Items Found:**\n"
            "- Painting — Gallery (R51) (taken, scores +4; placed in trophy case, scores +6)\n"
            "- Sword — Living Room (R1) (taken; dropped in Gallery R51)\n"
            "- Rope — Attic (R10) (taken; lost during fight in Treasure Room)\n"
            "- Nasty knife — Attic (R10) (taken; deposited in trophy case R1)\n"
        )
        result = _dedup_items_found(kb)
        sections = _parse_sections(result)
        assert len(sections["Items Found"]) == 4
        # Check that drop annotations are gone
        for bullet in sections["Items Found"]:
            assert "dropped" not in bullet
            assert "deposited" not in bullet
            assert "placed" not in bullet
            assert "lost during" not in bullet

    def test_taken_preserved_after_stripping(self):
        """The (taken) or (taken, scores +N) portion should survive."""
        kb = (
            "**Items Found:**\n"
            "- Sword — Living Room (R1) (taken; dropped in Studio R52)\n"
        )
        result = _dedup_items_found(kb)
        sections = _parse_sections(result)
        assert "(taken)" in sections["Items Found"][0]

    def test_non_items_sections_untouched(self):
        """Other sections should pass through without modification."""
        kb = (
            "**Score Changes:**\n"
            "- take painting at Gallery (score 4->8, +4)\n"
            "- take painting at Gallery (score 10->14, +4)\n"
            "\n"
            "**Items Found:**\n"
            "- Painting — Gallery (taken)\n"
            "- Painting — Gallery (taken; dropped in Studio)\n"
            "\n"
            "**Dangerous Areas:**\n"
            "- Cellar is pitch black without lantern\n"
            "- Cellar is pitch black without lantern\n"
        )
        result = _dedup_items_found(kb)
        sections = _parse_sections(result)
        # Score Changes should keep both entries (not deduped by this function)
        assert len(sections["Score Changes"]) == 2
        # Dangerous Areas should keep both entries
        assert len(sections["Dangerous Areas"]) == 2
        # Items Found should be deduped to 1
        assert len(sections["Items Found"]) == 1

    def test_end_to_end_polluted_kb(self):
        """A realistic polluted KB should collapse to clean unique entries."""
        kb = (
            "**Score Changes:**\n"
            "- take painting at Gallery (score 4->8, +4)\n"
            "\n"
            "**Items Found:**\n"
            "- Leaflet — West House mailbox (taken)\n"
            "- Sword — Living Room (taken)\n"
            "- Painting — Gallery (taken, scores +4)\n"
            "- Leaflet — West House mailbox (taken); dropped in Maintenance Room, re-taken\n"
            "- Sword — Living Room (R1) (taken; dropped in Gallery to reduce weight)\n"
            "- Painting — Gallery (R51) (taken, scores +4; placed in trophy case, scores +6)\n"
            "- Painting — Gallery (R51) (taken; deposited in trophy case R1)\n"
            "- Painting — Gallery (R51) (taken)\n"
            "- Painting — Gallery (R51) (taken, scores +4; note: score change not in verified list for this episode)\n"
            "- Platinum bar — Loud Room (cannot be taken — all commands echo)\n"
            "- Platinum bar — Loud Room (R58) (taken after `echo`)\n"
            "- Platinum bar — Loud Room (R58) (taken; dropped in Studio R52)\n"
            "- Platinum bar — Loud Room (R58) (taken; deposited in trophy case R1)\n"
            "- Nasty knife — Attic (R10) (taken; dropped in Gallery)\n"
            "- Nasty knife — Attic (R10) (taken; dropped in Studio R52)\n"
            "- Rope — Attic (R10) (taken; dropped in Studio)\n"
            "- Rope — Attic (R10) (taken; tied to railing in Dome Room R29)\n"
            "\n"
            "**Dangerous Areas:**\n"
            "- Cellar is pitch black without lantern\n"
        )
        result = _dedup_items_found(kb)
        sections = _parse_sections(result)

        # Should have exactly 6 unique items
        assert len(sections["Items Found"]) == 6
        item_names = []
        for bullet in sections["Items Found"]:
            raw = bullet.lstrip("- ").lstrip("* ").lstrip("+ ")
            name = raw.split(" — ")[0].split(" at ")[0].strip()
            item_names.append(name)
        assert "Leaflet" in item_names
        assert "Sword" in item_names
        assert "Painting" in item_names
        assert "Platinum bar" in item_names
        assert "Nasty knife" in item_names
        assert "Rope" in item_names

        # No drop annotations in any Items Found bullet
        for bullet in sections["Items Found"]:
            assert "dropped" not in bullet.lower()
            assert "deposited" not in bullet.lower()

        # Score Changes and Dangerous Areas untouched
        assert len(sections["Score Changes"]) == 1
        assert len(sections["Dangerous Areas"]) == 1

    def test_no_items_found_section_passthrough(self):
        """KB without Items Found section should pass through unchanged."""
        kb = (
            "**Score Changes:**\n"
            "- take painting at Gallery (score 4->8, +4)\n"
        )
        result = _dedup_items_found(kb)
        assert result == kb

    def test_standalone_drop_entry_skipped(self):
        """Entries like '- Leaflet — dropped in Troll Room' with no spawn info should be removed."""
        kb = (
            "**Items Found:**\n"
            "- Leaflet — West House mailbox (taken)\n"
            "- Leaflet — dropped in Troll Room (before entering maze)\n"
        )
        result = _dedup_items_found(kb)
        sections = _parse_sections(result)
        assert len(sections["Items Found"]) == 1
        assert "West House" in sections["Items Found"][0]

    def test_note_annotations_stripped(self):
        """Episode-specific note annotations should be stripped."""
        kb = (
            "**Items Found:**\n"
            "- Painting — Gallery (R51) (taken, scores +4; note: score change not in verified list for this episode)\n"
        )
        result = _dedup_items_found(kb)
        sections = _parse_sections(result)
        assert len(sections["Items Found"]) == 1
        assert "note:" not in sections["Items Found"][0]
        assert "scores +4" in sections["Items Found"][0]

    def test_case_insensitive_dedup(self):
        """Item name matching should be case-insensitive."""
        kb = (
            "**Items Found:**\n"
            "- Brass lantern — Living Room (R1) (taken)\n"
            "- brass lantern — Living Room (R1) (taken; dropped in Cellar)\n"
        )
        result = _dedup_items_found(kb)
        sections = _parse_sections(result)
        assert len(sections["Items Found"]) == 1
