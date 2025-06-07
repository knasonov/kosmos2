import argparse
import db


def main():
    parser = argparse.ArgumentParser(description="Manage user limits")
    sub = parser.add_subparsers(dest="cmd", required=True)

    add_p = sub.add_parser("add", help="Add or update a user")
    add_p.add_argument("username")
    add_p.add_argument("password")
    add_p.add_argument("limit", type=float)

    pw_p = sub.add_parser("set-password", help="Change a user's password")
    pw_p.add_argument("username")
    pw_p.add_argument("password")

    lim_p = sub.add_parser("set-limit", help="Set remaining minutes for a user")
    lim_p.add_argument("username")
    lim_p.add_argument("limit", type=float)

    list_p = sub.add_parser("list", help="List users")

    args = parser.parse_args()

    db.init_db()
    db.populate_defaults()

    if args.cmd == "add":
        db.add_user(args.username, args.password, args.limit)
    elif args.cmd == "set-password":
        db.set_password(args.username, args.password)
    elif args.cmd == "set-limit":
        db.set_limit(args.username, args.limit)
    elif args.cmd == "list":
        for row in db.list_users():
            print(f"{row['username']}: {row['minutes_remaining']} minutes")


if __name__ == "__main__":
    main()
