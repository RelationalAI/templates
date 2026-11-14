"""Tour report: reads the deployed traveling_salesman model.

Run `python -m queries.tour` after `rai models deploy --path model`. Prints the status and
objective of the latest refresh's solve, and the edges of the shortest tour.
"""

from model import Edge, SolveStatus, TourDistance, model

if __name__ == "__main__":
    status = model.select(SolveStatus).to_df().iloc[:, 0].tolist()
    distance = model.select(TourDistance).to_df().iloc[:, 0].tolist()
    print(f"\nSolve result:\n• status: {', '.join(status)}")
    if distance:
        print(f"• objective: {round(distance[0], 9)}\n")
        print(f"HiGHS: {status[0]}, tour distance={distance[0]:.1f}")

    print("\nTour edges:")
    model.select(Edge.i.alias("from"), Edge.j.alias("to")).where(Edge.x > 0.5).inspect()
