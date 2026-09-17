from tvagent.speaker_eval import EvalCase, best_by_grid, score_cases


def test_score_cases_all_correct():
    # 2 enrolled-person clips, both correctly identified; 1 stranger clip, correctly GUEST.
    cases = [
        EvalCase(true="dad", predicted="dad"),
        EvalCase(true="mom", predicted="mom"),
        EvalCase(true="stranger", predicted="guest"),
    ]
    report = score_cases(cases)
    assert report.correct_rate == 1.0
    assert report.stranger_reject_rate == 1.0


def test_score_cases_mixed_asymmetric():
    # 3 enrolled-person clips (2 correct, 1 wrong) vs 2 stranger clips (1 correctly
    # rejected, 1 leaked through as a false match) -- denominators differ (3 vs 2)
    # so a numerator/denominator swap would fail this.
    cases = [
        EvalCase(true="dad", predicted="dad"),
        EvalCase(true="dad", predicted="dad"),
        EvalCase(true="mom", predicted="guest"),  # missed match
        EvalCase(true="stranger", predicted="guest"),
        EvalCase(true="stranger", predicted="dad"),  # false accept
    ]
    report = score_cases(cases)
    assert report.correct_rate == 2 / 3
    assert report.stranger_reject_rate == 0.5
    assert report.confusion[("mom", "guest")] == 1
    assert report.confusion[("stranger", "dad")] == 1


def test_score_cases_no_enrolled_clips_correct_rate_is_none():
    cases = [EvalCase(true="stranger", predicted="guest")]
    report = score_cases(cases)
    assert report.correct_rate is None
    assert report.stranger_reject_rate == 1.0


def test_score_cases_no_stranger_clips_reject_rate_is_none():
    cases = [EvalCase(true="dad", predicted="dad")]
    report = score_cases(cases)
    assert report.correct_rate == 1.0
    assert report.stranger_reject_rate is None


def test_best_by_grid_picks_balanced_objective():
    # objective = min(correct_rate, stranger_reject_rate); grid[2] wins on that,
    # even though grid[1] has the higher correct_rate alone.
    grid = [
        (0.2, 0.05, 0.5, 0.5),  # min = 0.5
        (0.3, 0.10, 1.0, 0.4),  # min = 0.4
        (0.4, 0.15, 0.8, 0.8),  # min = 0.8 <- best
    ]
    assert best_by_grid(grid) == (0.4, 0.15)


def test_best_by_grid_ties_take_first_in_grid_order():
    grid = [
        (0.2, 0.05, 0.7, 0.7),  # min = 0.7, first
        (0.3, 0.10, 0.7, 0.7),  # min = 0.7, tie -> not picked
    ]
    assert best_by_grid(grid) == (0.2, 0.05)
