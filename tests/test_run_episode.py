"""Tests for run_episode output format helpers."""
import pytest


def test_format_turn_line_basic():
    from run_episode import format_turn_line
    line = format_turn_line(
        turn_num=1,
        loc="West of House",
        score=0,
        max_score=350,
        critic=0.75,
        rejections=0,
        action="open mailbox",
    )
    assert line == "TURN 1 | loc=West_of_House | score=0/350 | critic=0.75 | rejections=0 | action=open mailbox"


def test_format_turn_line_spaces_in_loc():
    from run_episode import format_turn_line
    line = format_turn_line(
        turn_num=5,
        loc="North of House",
        score=10,
        max_score=350,
        critic=0.40,
        rejections=2,
        action="go north",
    )
    assert "loc=North_of_House" in line
    assert "rejections=2" in line


def test_format_turn_line_empty_loc():
    from run_episode import format_turn_line
    line = format_turn_line(
        turn_num=1, loc="", score=0, max_score=350, critic=0.0, rejections=0, action="look"
    )
    assert "loc=unknown" in line


def test_format_episode_end():
    from run_episode import format_episode_end
    line = format_episode_end(
        turns=47,
        score=10,
        max_score=350,
        locations=3,
        objectives_found=2,
        reason="game_over_death",
    )
    assert line == "EPISODE_END | turns=47 | score=10/350 | locations=3 | objectives_found=2 | reason=game_over_death"


def test_format_episode_end_win():
    from run_episode import format_episode_end
    line = format_episode_end(
        turns=100, score=350, max_score=350, locations=20, objectives_found=10, reason="game_over_win"
    )
    assert "reason=game_over_win" in line
    assert "score=350/350" in line


def test_argparse_defaults(monkeypatch):
    import sys
    monkeypatch.setattr(sys, "argv", ["run_episode.py"])
    # Import and call the parser directly without running main()
    from run_episode import _build_parser
    args = _build_parser().parse_args([])
    assert args.max_turns == 100
    assert args.episode_id is None


def test_argparse_custom_values(monkeypatch):
    from run_episode import _build_parser
    args = _build_parser().parse_args(["--max-turns", "25", "--episode-id", "test01"])
    assert args.max_turns == 25
    assert args.episode_id == "test01"
