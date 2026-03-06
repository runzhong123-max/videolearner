from app.db.database import Database


def main() -> int:
    db = Database()
    db.initialize()
    print(f"Database initialized: {db.as_path()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
