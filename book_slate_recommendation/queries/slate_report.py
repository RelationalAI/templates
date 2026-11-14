"""Book slate report: reads the deployed book_slate_recommendation model.

Run `python -m queries.slate_report` after `rai models deploy --path model`. Prints the
formulation, a per-user feasibility check of the candidate set, the solve-result block, the
chosen slate ordered by slot (1..K), the per-user subject distribution, the per-pick
explanation-path support, and a verbose diagnostic block (candidate set and
structural-embeddedness map) at the end. The report accepts an OPTIMAL slate, or a
TIME_LIMIT slate with an objective (the best found when the time limit ends the search),
and stops on any other termination status.
"""

from model import (
    COLD_START_CAP,
    EXPLANATION_FLOOR,
    FRESH_WINDOW_DAYS,
    FRESHNESS_FLOOR,
    HERO_EMBEDDEDNESS_THRESHOLD,
    MAX_HOPS,
    MAX_PER_SUBJECT,
    ORIGINALS_FLOOR,
    SLATE_SIZE_K,
    WEAK_EXPLANATION_THRESHOLD,
    Author,
    Book,
    Candidate,
    SolveStatus,
    Subject,
    TotalSupport,
    User,
    model,
    problem,
)
from relationalai.semantics import Integer, count


# explanation_ic requires sum((K+1-slot)*path_count_total) >= EXPLANATION_FLOOR.
# The maximum achievable score per user is obtained by sorting their unread
# candidates by path_count_total descending, taking the top K, and weighting
# them with K, K-1, ..., 1. If that upper bound is below the floor, the IC
# cannot be satisfied regardless of the solver's choices.
def _max_explanation_score(group):
    top_k = group.nlargest(SLATE_SIZE_K).tolist()
    weights = range(SLATE_SIZE_K, SLATE_SIZE_K - len(top_k), -1)
    return int(sum(w * v for w, v in zip(weights, top_k)))


if __name__ == "__main__":
    problem.display()

    # Per-user floor check: per-user floor ICs anchor on Candidate rows, so a
    # user with no candidates left after exclude_read is silently skipped
    # instead of flagged as infeasible. Compute the unread candidate set per
    # user explicitly and refuse to report if any user fails any of the per-IC
    # feasibility necessary conditions below, so sparse customer reach hits a
    # clear Python-level error.
    candidate_df = model.select(
        Candidate.user_id.alias("user_id"),
        Candidate.book_id.alias("book_id"),
        Candidate.path_count_total.alias("path_count_total"),
    ).to_df()
    for col in ("user_id", "book_id", "path_count_total"):
        candidate_df[col] = candidate_df[col].astype(int)
    # The read history, book attributes, authorship, subjects and users all
    # come from the deployed model.
    rating = Integer.ref()
    reads_df = model.select(
        User.id.alias("user_id"),
        Book.id.alias("book_id"),
    ).where(User.read(User, Book, rating)).to_df().astype(int)
    unread = candidate_df.merge(
        reads_df,
        on=["user_id", "book_id"],
        how="left",
        indicator=True,
    )
    unread = unread[unread["_merge"] == "left_only"][["user_id", "book_id", "path_count_total"]]
    # Pull triangle counts so the hero-eligible feasibility check can
    # count books meeting HERO_EMBEDDEDNESS_THRESHOLD per user.
    triangle_df = model.select(
        Book.id.alias("book_id"),
        Book.triangle_count.alias("triangle_count"),
    ).to_df()
    # PyRel returns Int128Array-backed columns; cast to native int so
    # pandas comparisons against Python ints work in the feasibility
    # checks below.
    triangle_df["book_id"] = triangle_df["book_id"].astype(int)
    triangle_df["triangle_count"] = triangle_df["triangle_count"].astype(int)
    books_df = model.select(
        Book.id.alias("book_id"),
        Book.age_days.alias("age_days"),
        Book.in_house.alias("in_house"),
    ).to_df().astype(int)
    book_authors_df = model.select(
        Book.id.alias("book_id"),
        Author.id.alias("author_id"),
    ).where(Book.written_by(Book, Author)).to_df().astype(int)
    book_subjects_df = model.select(
        Book.id.alias("book_id"),
        Subject.id.alias("subject_id"),
    ).where(Book.about(Book, Subject)).to_df().astype(int)
    unread_with_book = unread.merge(books_df, on="book_id", how="left").merge(
        triangle_df, on="book_id", how="left"
    )
    unread_authors = unread.merge(book_authors_df, on="book_id", how="left")
    unread_subjects = unread.merge(book_subjects_df, on="book_id", how="left")
    unread_counts = unread_with_book.groupby("user_id").size()
    fresh_counts = (
        unread_with_book[unread_with_book["age_days"] <= FRESH_WINDOW_DAYS].groupby("user_id").size()
    )
    in_house_counts = unread_with_book[unread_with_book["in_house"] == 1].groupby("user_id").size()
    hero_counts = (
        unread_with_book[unread_with_book["triangle_count"] >= HERO_EMBEDDEDNESS_THRESHOLD]
        .groupby("user_id")
        .size()
    )
    distinct_author_counts = unread_authors.groupby("user_id")["author_id"].nunique()
    distinct_subject_counts = unread_subjects.groupby("user_id")["subject_id"].nunique()
    # cold_start_ic caps weakly-explained picks at COLD_START_CAP per user;
    # the slate must be filled with K - COLD_START_CAP strongly-explained
    # (path_count_total >= WEAK_EXPLANATION_THRESHOLD) candidates at minimum.
    strong_counts = (
        unread[unread["path_count_total"] >= WEAK_EXPLANATION_THRESHOLD].groupby("user_id").size()
    )

    max_explanation = unread.groupby("user_id")["path_count_total"].apply(_max_explanation_score)

    all_users = set(model.select(User.id.alias("user_id")).to_df()["user_id"].astype(int))
    absent_from_unread = sorted(all_users - set(unread_counts.index))
    short_total = sorted(unread_counts[unread_counts < SLATE_SIZE_K].index.tolist())
    short_fresh = sorted(list(all_users - set(fresh_counts[fresh_counts >= FRESHNESS_FLOOR].index)))
    short_in_house = sorted(
        list(all_users - set(in_house_counts[in_house_counts >= ORIGINALS_FLOOR].index))
    )
    short_hero = sorted(list(all_users - set(hero_counts[hero_counts >= 1].index)))
    short_authors = sorted(
        list(all_users - set(distinct_author_counts[distinct_author_counts >= SLATE_SIZE_K].index))
    )
    # Subject-span feasibility: with K picks and MAX_PER_SUBJECT cap, the user's
    # pool must span at least ceil(K / MAX_PER_SUBJECT) distinct subjects.
    min_subjects = -(-SLATE_SIZE_K // MAX_PER_SUBJECT)  # ceil division
    short_subjects = sorted(
        list(all_users - set(distinct_subject_counts[distinct_subject_counts >= min_subjects].index))
    )
    # Cold-start feasibility: at least K - COLD_START_CAP strongly-explained picks
    # are required. If a user has fewer strong candidates, cold_start_ic forces
    # infeasibility.
    min_strong = max(0, SLATE_SIZE_K - COLD_START_CAP)
    short_strong = (
        sorted(list(all_users - set(strong_counts[strong_counts >= min_strong].index)))
        if min_strong > 0
        else []
    )
    short_explanation = sorted(
        list(all_users - set(max_explanation[max_explanation >= EXPLANATION_FLOOR].index))
    )
    if (
        absent_from_unread
        or short_total
        or short_fresh
        or short_in_house
        or short_hero
        or short_authors
        or short_subjects
        or short_strong
        or short_explanation
    ):
        raise SystemExit(
            "Per-user candidate floor violated:\n"
            f"  users absent from unread candidate table: {absent_from_unread}\n"
            f"  users with < SLATE_SIZE_K={SLATE_SIZE_K} unread candidates: {short_total}\n"
            f"  users with < FRESHNESS_FLOOR={FRESHNESS_FLOOR} unread fresh "
            f"(age_days <= {FRESH_WINDOW_DAYS}) candidates: {short_fresh}\n"
            f"  users with < ORIGINALS_FLOOR={ORIGINALS_FLOOR} unread in-house "
            f"candidates: {short_in_house}\n"
            f"  users with no unread hero-eligible (triangle_count >= "
            f"{HERO_EMBEDDEDNESS_THRESHOLD}) candidates: {short_hero}\n"
            f"  users with < SLATE_SIZE_K={SLATE_SIZE_K} distinct unread authors: {short_authors}\n"
            f"  users with < ceil(K/MAX_PER_SUBJECT)={min_subjects} distinct unread "
            f"subjects: {short_subjects}\n"
            f"  users with < K-COLD_START_CAP={min_strong} strongly-explained "
            f"(path_count_total >= {WEAK_EXPLANATION_THRESHOLD}) unread candidates: "
            f"{short_strong}\n"
            f"  users whose max achievable position-weighted explanation score < "
            f"EXPLANATION_FLOOR={EXPLANATION_FLOOR}: {short_explanation}\n"
            "Pick a strategy by which condition fired:\n"
            "  reach (absent_from_unread, short_total): densify Book.similar_to or "
            "the read history.\n"
            "  per-IC floor (short_fresh, short_in_house, short_hero, short_subjects, "
            "short_strong): lower the corresponding constant, or refresh the data slice "
            "with denser coverage in that dimension.\n"
            "  short_authors: lower SLATE_SIZE_K or use a corpus with more distinct "
            "authors per user reach.\n"
            "  short_explanation: lower EXPLANATION_FLOOR, or expand the candidate pool "
            "so per-user path_count_total distributions reach the threshold."
        )

    print("\nUnread candidate count per user (feasibility diagnostic):")
    print(unread_counts.sort_index().to_string())

    # Status and objective of the latest refresh's solve. A refresh records any
    # termination status, so the report checks it. The time limit can end the
    # search with the best slate found, which the report accepts.
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    support = model.select(TotalSupport).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if status not in (["OPTIMAL"], ["TIME_LIMIT"]) or not support:
        raise SystemExit(f"No slate: termination status {status}, objective {support}")
    print(f"• objective: {support[0]}")

    print("\nUsers in this run:")
    model.select(
        User.id.alias("user_id"),
        User.name.alias("user"),
    ).inspect()

    # Headline output: the chosen slate per user, ordered by slot
    # (1=hero/top of row, K=bottom).
    print(f"\nFinal slate per user (K = {SLATE_SIZE_K}, slot 1 = top of row):")
    b_pick = Book.ref()
    tc_pick = Integer.ref()
    slate_df = (
        model.select(
            Candidate.user_id.alias("user_id"),
            Candidate.slot.alias("slot"),
            Candidate.book_id.alias("book_id"),
            Candidate.path_count_total.alias("path_count_total"),
            tc_pick.alias("triangle_count"),
        )
        .where(
            Candidate.slot <= SLATE_SIZE_K,
            b_pick.id == Candidate.book_id,
            b_pick.triangle_count == tc_pick,
        )
        .to_df()
    )
    print(slate_df.sort_values(["user_id", "slot"]).to_string(index=False))

    print("\nSubject distribution per user's slate:")
    u_disp = User.ref()
    b_disp = Book.ref()
    s_disp = Subject.ref()
    model.select(
        u_disp.id.alias("user_id"),
        s_disp.name.alias("subject"),
        count(Candidate)
        .per(u_disp, s_disp)
        .where(
            Candidate.user_id == u_disp.id,
            Candidate.book_id == b_disp.id,
            Book.about(b_disp, s_disp),
            Candidate.slot <= SLATE_SIZE_K,
        )
        .alias("n_picked"),
    ).inspect()

    print("\nExplanation-path support per picked item (ordered by slot):")
    expl_df = (
        model.select(
            Candidate.user_id.alias("user_id"),
            Candidate.slot.alias("slot"),
            Candidate.book_id.alias("book_id"),
            Candidate.path_count_via_kg_walk.alias("paths_via_kg_walk"),
            Candidate.path_count_via_author.alias("paths_via_author"),
            Candidate.path_count_via_subject.alias("paths_via_subject"),
        )
        .where(Candidate.slot <= SLATE_SIZE_K)
        .to_df()
    )
    print(expl_df.sort_values(["user_id", "slot"]).to_string(index=False))

    # Diagnostics: candidate set sizing and structural-embeddedness map.

    print(
        f"\nCandidate set per user (Books reachable within {MAX_HOPS} hops over the heterogeneous KG):"
    )
    model.select(
        Candidate.user_id.alias("user_id"),
        Candidate.book_id.alias("book_id"),
        Candidate.path_count_total.alias("path_count_total"),
        Candidate.path_count_via_kg_walk.alias("paths_via_kg_walk"),
        Candidate.path_count_via_author.alias("paths_via_author"),
        Candidate.path_count_via_subject.alias("paths_via_subject"),
    ).inspect()

    print("\nBook structural embeddedness (similar_to triangle counts):")
    model.select(
        Book.id.alias("book_id"),
        Book.title.alias("title"),
        Book.triangle_count.alias("triangle_count"),
    ).inspect()
